from pathlib import Path
from typing import Any, Optional

import click
import typer
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
)
from rich.tree import Tree

from models.commons.storage.downloads import (
    DOWNLOAD_LARGE_FILE_THRESHOLD,
    download_file_with_size_optimization,
)
from models.commons.storage.r2 import (
    get_r2_client,
    get_r2_transfer_config,
)
from models.commons.util.config import r2_bucket_name

# Initialize Rich console for formatted output
console = Console()
r2_app = typer.Typer(
    help="Browse Cloudflare R2 storage (read-only: ls, download, cat, du).",
    no_args_is_help=True,
)


def format_r2_path(path: str) -> tuple[str, str]:
    """
    Convert an R2 URL-style path to bucket and key components.

    Args:
        path: String in format "r2://bucket-name/path/to/resource"

    Returns:
        tuple: (bucket_name, resource_path)

    Raises:
        click.BadParameter: If path doesn't start with "r2://"
    """
    if not path.startswith("r2://"):
        raise click.BadParameter("R2 path must start with r2://")

    parts = path[5:].split("/", 1)
    if len(parts) < 2:
        return parts[0], ""  # Just bucket name, no path

    bucket, path = parts
    return bucket, path


def list_r2_objects(  # noqa: C901
    bucket: str, prefix: Optional[str] = None, recursive: bool = False
) -> None:
    # Branching is inherent here: paginated listing plus recursive-tree vs. flat rendering.

    """
    List objects in an R2 bucket, with optional prefix and recursive listing.

    Args:
        bucket: Name of the R2 bucket
        prefix: Optional path prefix to list from
        recursive: If True, show all nested contents; if False, show only immediate children

    The output is formatted as a tree structure in recursive mode, or a flat list otherwise.
    Directories and files are marked with distinct icons (📁 for directories, 📄 for files).
    """

    r2_client = get_r2_client()

    try:
        # Normalize prefix with trailing slash
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        effective_prefix = prefix if prefix else ""
        files = set()
        common_prefixes = []

        if not recursive:
            # Non-recursive with Delimiter — still paginate since Contents
            # is capped at 1000 keys per page even with Delimiter set.
            paginator = r2_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(
                Bucket=bucket, Prefix=effective_prefix, Delimiter="/"
            ):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if not key.endswith("/"):
                        files.add(key)
                common_prefixes.extend(page.get("CommonPrefixes", []))
        else:
            # Recursive: paginate to handle >1000 objects
            paginator = r2_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=effective_prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if not key.endswith("/"):
                        files.add(key)

        # Handle empty results
        if not files and not common_prefixes:
            if prefix:
                console.print(f"No objects found in r2://{bucket}/{prefix}")
            else:
                console.print(f"No objects found in r2://{bucket}/")
            return

        if recursive:
            # Build and display tree structure for recursive listing
            tree_root = f"r2://{bucket}/{prefix if prefix else ''}"
            tree_root = tree_root.rstrip("/")
            tree = Tree(tree_root)

            for file_path in sorted(files):
                # Get relative path from prefix
                rel_path = file_path
                if prefix and file_path.startswith(prefix):
                    rel_path = file_path[len(prefix) :]

                parts = [p for p in rel_path.split("/") if p]
                if not parts:
                    continue

                # Build tree structure
                current = tree
                for part in parts[:-1]:
                    # Find or create directory node
                    found = False
                    for child in current.children:
                        # Labels are always plain strings here (we only ever add
                        # f"📁 {...}" / f"📄 {...}"); narrow the Rich RenderableType.
                        if isinstance(child.label, str) and child.label.endswith(part):
                            current = child
                            found = True
                            break

                    if not found:
                        current = current.add(f"📁 {part}")

                # Add file leaf
                current.add(f"📄 {parts[-1]}")

            console.print(tree)
        else:
            # Flat listing with full paths
            if common_prefixes:
                for prefix_obj in sorted(common_prefixes, key=lambda x: x["Prefix"]):
                    console.print(f"📁 r2://{bucket}/{prefix_obj['Prefix']}")

            for file_path in sorted(files):
                console.print(f"📄 r2://{bucket}/{file_path}")

    except ClientError as e:
        console.print(f"[red]Error accessing bucket {bucket}: {str(e)}[/red]")
        raise click.Abort() from e


def _download_one(
    r2_client: Any, bucket: str, key: str, local_path: str, file_size: int, label: str
) -> None:
    """Download a single file with progress bar (TTY) or optimized transfer (non-TTY)."""
    if console.is_terminal:
        dl_config = (
            get_r2_transfer_config()
            if file_size > DOWNLOAD_LARGE_FILE_THRESHOLD
            else None
        )
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task(f"Downloading {label}", total=max(file_size, 1))

            def callback(bytes_transferred: int, _task: TaskID = task) -> None:
                progress.update(_task, advance=bytes_transferred)

            r2_client.download_file(
                bucket, key, local_path, Callback=callback, Config=dl_config
            )
    else:
        download_file_with_size_optimization(
            r2_client, bucket, key, local_path, file_size
        )
        console.print(f"  Downloaded {label}")


def download_from_r2(
    r2_client: Any,
    bucket: str,
    key: str,
    dest_path: Path,
    dry_run: bool = False,
) -> None:
    """
    Download a single object or all objects under a prefix from R2 storage.

    Args:
        r2_client: Boto3 client pre-configured for R2
        bucket: Source R2 bucket
        key: Object key or prefix
        dest_path: Local destination (file or directory path)
        dry_run: If True, only show what would be downloaded
    """
    is_dir = _check_if_directory(r2_client, bucket, key) or key.endswith("/")

    if is_dir:
        if not key.endswith("/"):
            key += "/"

        paginator = r2_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=key):
            for obj in page.get("Contents", []):
                obj_key = obj["Key"]
                rel_part = Path(obj_key[len(key) :])
                local_file = dest_path / rel_part
                local_file.parent.mkdir(parents=True, exist_ok=True)

                if dry_run:
                    console.print(
                        f"[yellow]Would download: r2://{bucket}/{obj_key} -> {local_file}[/yellow]"
                    )
                    continue

                _download_one(
                    r2_client,
                    bucket,
                    obj_key,
                    str(local_file),
                    obj["Size"],
                    str(rel_part),
                )
    else:
        dest_file = dest_path
        if dest_file.is_dir():
            dest_file = dest_file / Path(key).name
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        if dry_run:
            console.print(
                f"[yellow]Would download: r2://{bucket}/{key} -> {dest_file}[/yellow]"
            )
            return

        head = r2_client.head_object(Bucket=bucket, Key=key)
        _download_one(
            r2_client,
            bucket,
            key,
            str(dest_file),
            head["ContentLength"],
            Path(key).name,
        )


@r2_app.command()
def ls(
    path: str = typer.Argument(None, help="R2 path in format r2://bucket/path"),
    recursive: bool = typer.Option(
        False, "--recursive", "-r", help="List contents recursively"
    ),
) -> None:
    """
    List objects in R2 bucket.

    Examples:
        # List contents of default bucket root
        bh r2 ls

        # List specific model directory
        bh r2 ls r2://biolm-public/biolm-hub/model-weights/models/esm2

        # List all contents recursively
        bh r2 ls r2://biolm-public/biolm-hub/model-weights/models/esm2 --recursive

        # List test data directory
        bh r2 ls r2://biolm-public/biolm-hub/test-data
    """
    try:
        if path:
            bucket, prefix = format_r2_path(path)
        else:
            bucket, prefix = r2_bucket_name, ""

        list_r2_objects(bucket, prefix, recursive)
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1) from e


@r2_app.command()
def download(
    source: str = typer.Argument(
        ..., help="R2 path to a file or prefix (r2://bucket/key)"
    ),
    destination: str = typer.Argument(
        ..., help="Local destination path (file or directory)"
    ),
    dry_run: bool = typer.Option(
        False, help="Show what would be downloaded without making changes"
    ),
) -> None:
    """
    Download a file or prefix from R2 to local storage (read-only).

    Examples:
        # Download a single file to the current directory
        bh r2 download r2://biolm-public/biolm-hub/test-data/foo.json .

        # Download an entire prefix to ./tmp
        bh r2 download r2://biolm-public/biolm-hub/test-data/ ./tmp

        # Preview a download without writing anything
        bh r2 download r2://biolm-public/biolm-hub/test-data/ ./tmp --dry-run
    """
    try:
        if not source.startswith("r2://"):
            console.print(
                "[red]Error: source must be an R2 path (r2://bucket/key).[/red]"
            )
            raise typer.Exit(1)
        if destination.startswith("r2://"):
            console.print(
                "[red]Error: destination must be a local path. "
                "`bh r2` is read-only and cannot write to R2.[/red]"
            )
            raise typer.Exit(1)

        bucket, key = format_r2_path(source)
        dest_path = Path(destination)
        r2_client = get_r2_client()

        if dest_path.exists() and dest_path.is_file() and key.endswith("/"):
            console.print(
                "[red]Error: Cannot download a directory into a single file.[/red]"
            )
            raise typer.Exit(1)

        download_from_r2(r2_client, bucket, key, dest_path, dry_run)

        if not dry_run:
            console.print("[green]Download completed successfully![/green]")

    except Exception as e:
        if isinstance(e, typer.Exit):
            raise
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1) from e


def _check_if_directory(r2_client: Any, bucket: str, key: str) -> bool:
    """Check if the given key represents a directory by looking for objects with that prefix."""
    # Check both with and without trailing slash
    prefix = key if key.endswith("/") else key + "/"
    list_response = r2_client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
    return bool(list_response.get("Contents"))


def _stream_file_content(streaming_body: StreamingBody) -> None:
    """Stream file content to stdout, handling binary data gracefully.

    Uses an incremental UTF-8 decoder so a multi-byte character that straddles a
    1 MB chunk boundary is decoded across chunks rather than failing. Decoding each
    chunk independently would corrupt boundary-straddling characters and wrongly
    reject a valid UTF-8 file as binary.
    """
    import codecs
    import sys

    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        # Stream in chunks for better memory efficiency with large files
        for chunk in streaming_body.iter_chunks(chunk_size=1024 * 1024):  # 1MB chunks
            text = decoder.decode(chunk)
            if text:
                sys.stdout.write(text)
                sys.stdout.flush()
        # Flush any bytes still buffered; an incomplete trailing sequence here
        # (final=True) raises UnicodeDecodeError -> genuinely not valid UTF-8.
        text = decoder.decode(b"", final=True)
        if text:
            sys.stdout.write(text)
            sys.stdout.flush()
    except UnicodeDecodeError:
        # Plain text to stderr (builtin print does not render Rich markup).
        print(
            "Error: File contains binary data, cannot display as text",
            file=sys.stderr,
        )
        raise typer.Exit(1) from None


@r2_app.command()
def cat(
    path: str = typer.Argument(
        ..., help="R2 path to a single file (r2://bucket/path/to/file)"
    ),
) -> None:
    """
    Display the contents of a text file from R2 storage.

    This command reads a single file from R2 and streams its contents to stdout,
    similar to the Unix cat command. Only text files are supported; binary files
    will raise an error.

    Examples:
        # Display a configuration file
        bh r2 cat r2://biolm-public/biolm-hub/test-data/models/chai1/input.json

        # Pipe output to jq for JSON processing
        bh r2 cat r2://biolm-public/biolm-hub/test-data/models/chai1/input.json | jq '.params'

        # Pipe to grep for searching
        bh r2 cat r2://biolm-public/biolm-hub/test-data/models/chai1/input.json | grep "name"

        # View with less for pagination
        bh r2 cat r2://biolm-public/biolm-hub/test-data/models/chai1/input.json | less
    """
    import sys

    try:
        bucket, key = format_r2_path(path)

        # Validate that key is provided and doesn't look like a directory
        if not key:
            print(
                "Error: Please specify a file path, not just a bucket", file=sys.stderr
            )
            raise typer.Exit(1)

        if key.endswith("/"):
            print(f"Error: Path appears to be a directory: {path}", file=sys.stderr)
            print("The cat command only works with individual files", file=sys.stderr)
            raise typer.Exit(1)

        r2_client = get_r2_client()

        # First check if this is actually a directory (has objects under it)
        if _check_if_directory(r2_client, bucket, key):
            print(f"Error: Path is a directory: {path}", file=sys.stderr)
            print("The cat command only works with individual files", file=sys.stderr)
            print("Use 'bh r2 ls' to list directory contents", file=sys.stderr)
            raise typer.Exit(1)

        # Now check if the object exists as a file
        try:
            r2_client.head_object(Bucket=bucket, Key=key)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                print(f"Error: File not found: {path}", file=sys.stderr)
                raise typer.Exit(1) from e
            else:
                print(f"Error accessing file: {str(e)}", file=sys.stderr)
                raise typer.Exit(1) from e

        # Get and stream the file content
        response = r2_client.get_object(Bucket=bucket, Key=key)
        streaming_body = response["Body"]

        _stream_file_content(streaming_body)

    except Exception as e:
        if not isinstance(e, typer.Exit):
            print(f"Error: {str(e)}", file=sys.stderr)
            raise typer.Exit(1) from e
        raise


@r2_app.command()
def du(  # noqa: C901
    path: str = typer.Argument(
        ..., help="R2 path to calculate folder size (e.g., r2://bucket/path)"
    ),
    per_file: bool = typer.Option(
        False, "--per-file", help="Show sizes for individual files"
    ),
) -> None:
    # Branching is inherent here: aggregates directory totals and optional per-file sizes.
    """
    Display the size of a folder in R2 storage.

    By default, shows directory-level totals. Use --per-file to list individual files.

    Examples:
        # Display directory-level totals
        bh r2 du r2://biolm-public/biolm-hub/model-weights/models/

        # Display directory-level totals for a specific subfolder
        bh r2 du r2://biolm-public/biolm-hub/model-weights/models/esm2/

        # Display directory size with file-level details
        bh r2 du r2://biolm-public/biolm-hub/model-weights/models/esm2/ --per-file
    """
    try:
        bucket, prefix = format_r2_path(path)
        r2_client = get_r2_client()

        if not prefix.endswith("/"):
            prefix += "/"

        total_size = 0
        dir_sizes: dict[str, int] = {}
        file_sizes: dict[str, int] = {}
        files: list[tuple[str, int]] = []

        # List objects and calculate size
        response = r2_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        while response.get("Contents"):
            for obj in response["Contents"]:
                key = obj["Key"]
                size = obj["Size"]

                # Get the relative path after the prefix
                relative_path = key[len(prefix) :] if key.startswith(prefix) else key

                # Determine if it's a file in current directory or in a subdirectory
                if "/" in relative_path:
                    # It's in a subdirectory - get the first directory component
                    dir_name = relative_path.split("/")[0]
                    dir_sizes[dir_name] = dir_sizes.get(dir_name, 0) + size
                else:
                    # It's a file in the current directory
                    file_sizes[relative_path] = size

                # Collect file data if per_file flag is set
                if per_file:
                    files.append((key, size))

                # Sum total size
                total_size += size

            # Handle truncated responses
            if response["IsTruncated"]:
                response = r2_client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=prefix,
                    ContinuationToken=response["NextContinuationToken"],
                )
            else:
                break

        # Format size as human-readable
        def format_size(size: float) -> str:
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if size < 1024:
                    return f"{size:.2f} {unit}"
                size /= 1024
            return f"{size:.2f} PB"

        # Aligned output formatting
        max_size_length = 10  # Fixed width for sizes (e.g., ' 12.15 GB')
        path_format = f"{{:<{max_size_length}}}  {{}}"

        # Print files in current directory if any
        if file_sizes:
            console.print("\n[bold]Files:[/bold]")
            for filename, size in sorted(file_sizes.items()):
                full_path = f"r2://{bucket}/{prefix}{filename}"
                formatted_size = format_size(size).rjust(max_size_length)
                console.print(path_format.format(formatted_size, full_path))

        # Print subdirectory totals if any
        if dir_sizes:
            console.print("\n[bold]Subdirectories:[/bold]")
            for dir_name, size in sorted(dir_sizes.items()):
                full_path = f"r2://{bucket}/{prefix}{dir_name}/"
                formatted_size = format_size(size).rjust(max_size_length)
                console.print(path_format.format(formatted_size, full_path))

        # Print per-file details if flag is set
        if per_file and files:
            console.print("\n[bold]All Files (Detailed):[/bold]")
            for key, size in files:
                full_path = f"r2://{bucket}/{key}"
                formatted_size = format_size(size).rjust(max_size_length)
                console.print(path_format.format(formatted_size, full_path))

        # Print total size
        console.print(f"\n[green]Total size: {format_size(total_size)}[/green]")

    except ClientError as e:
        console.print(f"[red]Error calculating folder size: {str(e)}[/red]")
        raise typer.Exit(1) from e


@r2_app.command(name="download-outputs")
def download_outputs(
    model: str = typer.Option(
        ..., "--model", help="Model name (e.g., rf3, chai1, esmfold)"
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Custom output directory (default: models/{model}/{model}_outputs)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be downloaded without making changes"
    ),
) -> None:
    """
    Download test fixture outputs for a model from R2 to a local directory.

    This command downloads all expected output files from test fixtures
    and saves them to a local directory with the '_outputs' suffix.

    Examples:
        # Download RF3 test fixture outputs
        bh r2 download-outputs --model rf3

        # Download antifold outputs with dry-run
        bh r2 download-outputs --model antifold --dry-run

        # Download to custom directory
        bh r2 download-outputs --model chai1 --output-dir ./my_outputs

        # Preview what would be downloaded
        bh r2 download-outputs --model boltzgen --dry-run
    """
    try:
        # Determine output directory
        if output_dir:
            dest_path = Path(output_dir)
        else:
            dest_path = Path(f"models/{model}/{model}_outputs")

        # Construct R2 prefix for test fixture outputs
        r2_prefix = f"test-data/models/{model}"
        r2_path = f"r2://{r2_bucket_name}/{r2_prefix}"

        console.print(f"📥 Downloading test fixture outputs for [cyan]{model}[/cyan]")
        console.print(f"   Source: [yellow]{r2_path}[/yellow]")
        console.print(f"   Destination: [green]{dest_path}[/green]")

        if dry_run:
            console.print("\n[yellow]DRY RUN - No files will be downloaded[/yellow]\n")

        # Create destination directory
        if not dry_run:
            dest_path.mkdir(parents=True, exist_ok=True)

        # Download all files from the R2 prefix
        r2_client = get_r2_client()
        download_from_r2(r2_client, r2_bucket_name, r2_prefix, dest_path, dry_run)

        if not dry_run:
            console.print(
                f"\n[green]✅ Successfully downloaded outputs to {dest_path}[/green]"
            )
        else:
            console.print(f"\n[yellow]Would download to: {dest_path}[/yellow]")

    except Exception as e:
        console.print(f"[red]Error downloading outputs: {str(e)}[/red]")
        raise typer.Exit(1) from e
