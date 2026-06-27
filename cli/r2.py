from pathlib import Path
from typing import Optional

import click
import typer
from botocore.exceptions import ClientError
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.tree import Tree

from models.commons.storage.downloads import (
    DOWNLOAD_LARGE_FILE_THRESHOLD,
    UPLOAD_SMALL_FILE_THRESHOLD,
    download_file_with_size_optimization,
    upload_file_with_size_optimization,
)
from models.commons.storage.r2 import (
    get_r2_client,
    get_r2_transfer_config,
    get_r2_upload_transfer_config,
)
from models.commons.util.config import r2_bucket_name

# Initialize Rich console for formatted output
console = Console()
r2_app = typer.Typer(
    help="Manage Cloudflare R2 storage resources.",
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
):
    # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

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
                        if child.label.endswith(part):
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


def should_ignore_path(path: Path) -> bool:
    """
    Check if a file path should be ignored during upload.

    Args:
        path: Path to check

    Returns:
        bool: True if path matches any ignore patterns, False otherwise

    Patterns include Python bytecode, Git files, test cache, and other temporary files.
    """
    patterns_to_ignore = [
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".git",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
        ".coverage",
        "*.egg-info",
    ]

    current = path
    while current != Path("."):
        name = current.name
        for pattern in patterns_to_ignore:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            else:
                if name == pattern:
                    return True
        current = current.parent
    return False


def _download_one(
    r2_client, bucket: str, key: str, local_path: str, file_size: int, label: str
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

            def callback(bytes_transferred, _task=task):
                progress.update(_task, advance=bytes_transferred)

            r2_client.download_file(
                bucket, key, local_path, Callback=callback, Config=dl_config
            )
    else:
        download_file_with_size_optimization(
            r2_client, bucket, key, local_path, file_size
        )
        console.print(f"  Downloaded {label}")


def _upload_one(
    r2_client, bucket: str, key: str, src_path: Path, file_size: int
) -> None:
    """Upload a single file with progress bar (TTY, large files) or optimized transfer."""
    if file_size > UPLOAD_SMALL_FILE_THRESHOLD and console.is_terminal:
        upload_config = get_r2_upload_transfer_config()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task(
                f"Uploading {src_path.name}", total=max(file_size, 1)
            )

            def callback(bytes_transferred):
                progress.update(task, advance=bytes_transferred)

            r2_client.upload_file(
                str(src_path), bucket, key, Callback=callback, Config=upload_config
            )
    else:
        upload_file_with_size_optimization(
            r2_client, bucket, key, str(src_path), file_size
        )
        size_str = (
            f"{file_size:,} bytes"
            if file_size <= UPLOAD_SMALL_FILE_THRESHOLD
            else f"{file_size / (1024 * 1024):.1f} MB"
        )
        console.print(f"  Uploaded {src_path.name} ({size_str})")


def download_from_r2(
    r2_client,
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


def upload_to_r2(src_path: Path, bucket: str, dest_key: str, dry_run: bool = False):
    """
    Upload a file or directory to R2 storage.

    Args:
        src_path: Local path to upload
        bucket: Destination R2 bucket
        dest_key: Destination key (path) in the bucket
        dry_run: If True, only show what would be uploaded without actual upload

    Features:
    - Size-based optimization (put_object for <10MB, upload_file for larger)
    - Progress bar with spinner for large file uploads (TTY only)
    - Recursive directory handling
    - Pattern-based file filtering
    - Dry-run capability
    """
    r2_client = get_r2_client()
    original_dest_key = dest_key
    dest_key = dest_key.rstrip("/")

    if src_path.is_file():
        if original_dest_key == "" or original_dest_key.endswith("/"):
            dest_key = f"{dest_key}/{src_path.name}" if dest_key else src_path.name

        if should_ignore_path(src_path):
            return

        if dry_run:
            console.print(
                f"[yellow]Would upload: {src_path} -> r2://{bucket}/{dest_key}[/yellow]"
            )
            return

        try:
            _upload_one(r2_client, bucket, dest_key, src_path, src_path.stat().st_size)
        except ClientError as e:
            console.print(f"[red]Error uploading {src_path}: {str(e)}[/red]")
            raise click.Abort() from e

    elif src_path.is_dir():
        for item in src_path.rglob("*"):
            if item.is_file() and not should_ignore_path(item):
                relative_path = item.relative_to(src_path)
                new_key = (
                    f"{dest_key}/{relative_path}" if dest_key else str(relative_path)
                )
                upload_to_r2(item, bucket, new_key, dry_run)

    else:
        console.print(f"[red]Path not found: {src_path}[/red]")
        raise click.Abort()


def delete_r2_objects(bucket: str, prefix: str, dry_run: bool = False) -> None:
    """Delete objects in R2 bucket with given prefix or exact key."""
    r2_client = get_r2_client()

    try:
        # First check if this is an exact file match
        try:
            r2_client.head_object(Bucket=bucket, Key=prefix)
            # It's a single file
            objects = [{"Key": prefix}]
        except ClientError:
            # Not a single file, paginate to list all objects under the prefix
            objects = []
            paginator = r2_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                objects.extend(page.get("Contents", []))

            if not objects:
                console.print(f"No objects found at r2://{bucket}/{prefix}")
                return

        total_objects = len(objects)

        if dry_run:
            console.print("\nWould delete the following objects:")
            for obj in objects:
                console.print(f"📄 r2://{bucket}/{obj['Key']}")
            console.print(f"\nTotal: {total_objects} objects would be deleted")
            return

        # Confirm deletion
        console.print(
            f"\nFound {total_objects} objects to delete in r2://{bucket}/{prefix}"
        )
        for obj in objects:
            console.print(f"📄 r2://{bucket}/{obj['Key']}")

        confirm = typer.confirm(
            "\nAre you sure you want to delete these objects?", default=False
        )
        if not confirm:
            console.print("[yellow]Deletion cancelled.[/yellow]")
            raise typer.Exit()

        # Delete objects with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ) as progress:
            task = progress.add_task("Deleting objects...", total=total_objects)

            for obj in objects:
                r2_client.delete_object(Bucket=bucket, Key=obj["Key"])
                progress.advance(task)

        console.print("[green]Successfully deleted all objects![/green]")

    except ClientError as e:
        console.print(f"[red]Error deleting objects: {str(e)}[/red]")
        raise typer.Exit(1) from e


@click.group()
def r2():
    """
    Manage Cloudflare R2 storage resources.

    This command group provides tools for interacting with Cloudflare R2 storage:
    • ls: List bucket contents
    • cp: Copy files **between local storage and R2** (upload or download; files or directories)
    • cat: Display contents of text files
    • du: Display directory size or file-level sizes in R2 storage
    • rm: Remove files and directories recursively

    Examples:
        # List root contents
        bm r2 ls

        # List model directory with tree view
        bm r2 ls -r r2://biolm-modal/model-store/esm2

        # Upload a model directory
        bm r2 cp models/esm2 r2://biolm-modal/model-store/esm2/v1

        # Download a single file to current directory
        bm r2 cp r2://biolm-modal/test-data/foo.json .

        # Download an entire prefix to ./tmp (dry-run)
        bm r2 cp r2://biolm-modal/test-data/ ./tmp --dry-run

        # Preview upload with dry-run
        bm r2 cp models/esm2 r2://biolm-modal/model-store/esm2/v1 --dry-run

        # Display contents of a configuration file
        bm r2 cat r2://biolm-modal/test-data/models/chai1/input.json

        # Pipe JSON to jq
        bm r2 cat r2://biolm-modal/test-data/models/chai1/input.json | jq '.params'

        # Directory-level totals
        bm r2 du r2://biolm-modal/model-store/

        # Directory size with file details
        bm r2 du r2://biolm-modal/model-store/ --per-file

        # Preview deletion
        bm r2 rm r2://biolm-modal/test-qamar --dry-run

        # Remove directory and contents (requires confirmation)
        bm r2 rm r2://biolm-modal/test-qamar
    """
    pass


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
        bm r2 ls

        # List specific model directory
        bm r2 ls r2://biolm-modal/model-store/esm2

        # List all contents recursively
        bm r2 ls r2://biolm-modal/model-store/esm2 --recursive

        # List test data directory
        bm r2 ls r2://biolm-modal/test-data
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
def cp(
    source: str = typer.Argument(..., help="Local path or R2 path (r2://bucket/key)"),
    destination: str = typer.Argument(
        ..., help="R2 path (for upload) or local path (for download)"
    ),
    dry_run: bool = typer.Option(
        False, help="Show what would be copied without making changes"
    ),
) -> None:
    """
    Copy files between local storage and R2.

    Examples:
        # Upload a single model file
        bm r2 cp models/esm2/model.pt r2://biolm-modal/model-store/esm2/v1/

        # Upload entire model directory with dry-run
        bm r2 cp models/esm2 r2://biolm-modal/model-store/esm2 --dry-run

        # Download a remote file to current directory
        bm r2 cp r2://biolm-modal/test-data/foo.txt .

        # Download a remote folder to ./tmp
        bm r2 cp r2://biolm-modal/test-data/ ./tmp --dry-run
    """
    try:
        # Remote → Local
        if source.startswith("r2://") and not destination.startswith("r2://"):
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
            return

        # Local → Remote
        if source.startswith("r2://"):
            console.print(
                "[red]Downloading from R2 requires local destination; "
                "destination path appears to be remote.[/red]"
            )
            raise typer.Exit(1)

        src_path = Path(source)
        bucket, dest_key = format_r2_path(destination)

        if not src_path.exists():
            console.print(f"[red]Source path does not exist: {source}[/red]")
            raise typer.Exit(1)

        warn_as_dir = False
        if src_path.is_dir() and not dest_key.endswith("/"):
            dest_key += "/"
            warn_as_dir = True

        upload_to_r2(src_path, bucket, dest_key, dry_run)

        if warn_as_dir and not dry_run:
            console.print(
                f"[yellow]Interpreting destination r2://{bucket}/{dest_key.rstrip('/')} "
                "as a directory.[/yellow]"
            )

        if not dry_run:
            console.print("[green]Upload completed successfully![/green]")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1) from e


def _check_if_directory(r2_client, bucket: str, key: str) -> bool:
    """Check if the given key represents a directory by looking for objects with that prefix."""
    # Check both with and without trailing slash
    prefix = key if key.endswith("/") else key + "/"
    list_response = r2_client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
    return bool(list_response.get("Contents"))


def _stream_file_content(streaming_body) -> None:
    """Stream file content to stdout, handling binary data gracefully."""
    import sys

    try:
        # Stream in chunks for better memory efficiency with large files
        for chunk in streaming_body.iter_chunks(chunk_size=1024 * 1024):  # 1MB chunks
            text = chunk.decode("utf-8")
            sys.stdout.write(text)
            sys.stdout.flush()
    except UnicodeDecodeError:
        # Use standard print to stderr for error messages
        print(
            "[red]Error: File contains binary data, cannot display as text[/red]",
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
        bm r2 cat r2://biolm-modal/test-data/models/chai1/input.json

        # Pipe output to jq for JSON processing
        bm r2 cat r2://biolm-modal/test-data/models/chai1/input.json | jq '.params'

        # Pipe to grep for searching
        bm r2 cat r2://biolm-modal/test-data/models/chai1/input.json | grep "name"

        # View with less for pagination
        bm r2 cat r2://biolm-modal/test-data/models/chai1/input.json | less
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
            print("Use 'bm r2 ls' to list directory contents", file=sys.stderr)
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
    # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.
    """
    Display the size of a folder in R2 storage.

    By default, shows directory-level totals. Use --per-file to list individual files.

    Examples:
        # Display directory-level totals
        bm r2 du r2://biolm-modal/model-store/

        # Display directory-level totals for a specific subfolder
        bm r2 du r2://biolm-modal/model-store/esm2/

        # Display directory size with file-level details
        bm r2 du r2://biolm-modal/model-store/esm2/ --per-file
    """
    try:
        bucket, prefix = format_r2_path(path)
        r2_client = get_r2_client()

        if not prefix.endswith("/"):
            prefix += "/"

        total_size = 0
        dir_sizes = {}
        file_sizes = {}
        files = []

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
        def format_size(size: int) -> str:
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


@r2_app.command()
def rm(
    path: str = typer.Argument(..., help="R2 path to delete (r2://bucket/path)"),
    dry_run: bool = typer.Option(
        False, help="Show what would be deleted without making changes"
    ),
) -> None:
    """
    Remove objects from R2 storage (single file or directory).

    Requires confirmation before deletion.

    Examples:
        # Delete a single file
        bm r2 rm r2://biolm-modal/test-data/models/esm2/3b_encode.json

        # Preview deletion (dry run)
        bm r2 rm r2://biolm-modal/test-qamar --dry-run

        # Delete a directory and all its contents
        bm r2 rm r2://biolm-modal/test-qamar/

        # Delete a specific model version
        bm r2 rm r2://biolm-modal/model-store/esm2/v1/
    """
    try:
        bucket, prefix = format_r2_path(path)

        if not prefix:
            console.print(
                "[red]Error: Cannot delete bucket root. Please specify a path.[/red]"
            )
            raise typer.Exit(1)

        # Don't automatically append slash - let delete_r2_objects handle file vs directory
        delete_r2_objects(bucket, prefix, dry_run)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1) from e


@r2_app.command(name="download-outputs")
def download_outputs(
    model: str = typer.Option(
        ..., "--model", help="Model name (e.g., rfd3, rf3, chai1)"
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
        bm r2 download-outputs --model rf3

        # Download RFD3 outputs with dry-run
        bm r2 download-outputs --model rfd3 --dry-run

        # Download to custom directory
        bm r2 download-outputs --model chai1 --output-dir ./my_outputs

        # Preview what would be downloaded
        bm r2 download-outputs --model boltz --dry-run
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
