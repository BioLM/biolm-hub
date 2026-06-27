from decimal import Decimal
from typing import Optional

from gateway.model_discovery import get_model_mapper

# BILLING CONSTANTS - SOURCE OF TRUTH


# The markup multiplier applied to all base Modal costs
# This is the authoritative value that should match the external service
BILLING_MULTIPLIER = Decimal("2.25")

# Base cost per second for each Modal resource type (in USD)
# These are the raw costs before the multiplier is applied
MODAL_RESOURCE_BASE_COSTS = {
    "memory_gb": Decimal("0.000006670000"),
    "cpu_core": Decimal("0.000038000000"),
    "t4": Decimal("0.000164000000"),
    "l4": Decimal("0.000222000000"),
    "a10g": Decimal("0.000306000000"),
    "l40s": Decimal("0.000542000000"),
    "a100-40gb": Decimal("0.000772000000"),
    "a100-80gb": Decimal("0.000944000000"),
    "h200": Decimal("0.001261000000"),
    "h100": Decimal("0.001267000000"),
    "b200": Decimal("0.001736000000"),
}

# Special cache cost calculation: cpu_core*2 + 60*memory_gb
# This will be calculated dynamically when needed


# BILLING CALCULATION FUNCTIONS


def get_biolm_cost_per_second(resource_type: str) -> Decimal:
    """
    Get the marked-up cost per second for a given resource type.

    Args:
        resource_type: The Modal resource type (e.g., 'cpu_core', 'a100-80gb')

    Returns:
        The cost per second with markup applied

    Raises:
        KeyError: If the resource type is not found
    """
    if resource_type == "cache":
        # Cache cost is calculated as: cpu_core*2 + 60*memory_gb
        cpu_base = MODAL_RESOURCE_BASE_COSTS["cpu_core"]
        memory_base = MODAL_RESOURCE_BASE_COSTS["memory_gb"]
        cache_base_cost = cpu_base * 2 + memory_base * 60
        return cache_base_cost * BILLING_MULTIPLIER

    base_cost = MODAL_RESOURCE_BASE_COSTS[resource_type]
    return base_cost * BILLING_MULTIPLIER


def calculate_total_cost_per_second(
    cpu_count: int,
    gpu_type: Optional[str] = None,
    gpu_count: int = 0,
    max_req_ram_gb: Decimal = Decimal("0"),
    volume_req_gb: Decimal = Decimal("0"),
) -> Decimal:
    """
    Calculate the total cost per second for a container based on its resource specification.

    This mirrors the biolm_charge_per_s() method from the external service.

    Args:
        cpu_count: Number of CPU cores requested
        gpu_type: Type of GPU (e.g., 'a100-80gb', 't4', etc.)
        gpu_count: Number of GPUs requested
        max_req_ram_gb: Maximum RAM requested in GB
        volume_req_gb: Volume storage requested in GB

    Returns:
        Total cost per second for the container
    """
    total_cost = Decimal("0")

    # 1. CPU Charge: (cpu_count + 4) * cost_per_cpu_core
    # The +4 is a platform buffer as noted in the external service
    cpu_cost_per_second = get_biolm_cost_per_second("cpu_core")
    cpu_charge = (cpu_count + 4) * cpu_cost_per_second
    total_cost += cpu_charge

    # 2. GPU Charge: gpu_count * cost_per_gpu_type
    if gpu_type and gpu_count > 0:
        gpu_cost_per_second = get_biolm_cost_per_second(gpu_type)
        gpu_charge = gpu_count * gpu_cost_per_second
        total_cost += gpu_charge

    # 3. Memory or Volume Charge: max(RAM_charge, Volume_charge)
    memory_cost_per_second = get_biolm_cost_per_second("memory_gb")

    # RAM charge
    ram_charge = max_req_ram_gb * memory_cost_per_second

    # Volume charge (with 20:1 pricing ratio)
    volume_charge = (volume_req_gb / Decimal("20.0")) * memory_cost_per_second

    # Take the maximum of RAM or volume charge
    memory_or_volume_charge = max(ram_charge, volume_charge)
    total_cost += memory_or_volume_charge

    return total_cost


def _get_model_spec(model_slug: str) -> dict:
    """Looks up and returns the resource spec dictionary for a given model slug."""
    model_mapper = get_model_mapper()

    variant_info = model_mapper.get_variant_info(model_slug)
    if not variant_info:
        raise ValueError(f"Unknown model slug: {model_slug}")

    modal_app_name = variant_info["modal_app_name"]

    spec_dict = model_mapper.get_resource_spec(modal_app_name)
    if not spec_dict:
        raise ValueError(f"No resource spec found for app: {modal_app_name}")
    return spec_dict


def calculate_execution_cost(
    model_slug: str, estimated_seconds: Decimal = Decimal("5.0")
) -> Decimal:
    """
    Estimate the total cost for a request to a specific model.

    Args:
        model_slug: The API model slug (e.g., 'esm2-650m')
        estimated_seconds: Estimated execution time in seconds

    Returns:
        Estimated total cost for the request

    Raises:
        ValueError: If the model_slug is not found or resource specs are invalid
    """
    spec_dict = _get_model_spec(model_slug)

    # Extract resource requirements
    cpu_count = spec_dict.get("cpu", 1)
    gpu_type = spec_dict.get("gpu")
    gpu_count = spec_dict.get("gpu_count", 1 if gpu_type else 0)
    max_req_ram_gb = Decimal(str(spec_dict.get("memory", 4)))  # Default 4GB
    volume_req_gb = Decimal(str(spec_dict.get("disk_size", 10)))  # Default 10GB

    # Calculate cost per second
    cost_per_second = calculate_total_cost_per_second(
        cpu_count=cpu_count,
        gpu_type=gpu_type,
        gpu_count=gpu_count,
        max_req_ram_gb=max_req_ram_gb,
        volume_req_gb=volume_req_gb,
    )

    # Calculate total estimated cost
    total_cost = cost_per_second * estimated_seconds

    return total_cost


def get_all_resource_costs() -> dict[str, Decimal]:
    """
    Get all resource costs with markup applied.

    Returns:
        Dictionary mapping resource types to their marked-up costs per second
    """
    costs = {}
    for resource_type in MODAL_RESOURCE_BASE_COSTS:
        costs[resource_type] = get_biolm_cost_per_second(resource_type)

    # Add cache cost
    costs["cache"] = get_biolm_cost_per_second("cache")

    return costs


def get_hardware_spec_name(model_slug: str) -> str:
    """
    Get the hardware specification name for billing purposes.

    Returns the hardware spec name that matches MODAL_RESOURCE_BASE_COSTS keys,
    which is what Django expects in the usage events.

    Args:
        model_slug: The API model slug (e.g., 'esm2-650m')

    Returns:
        Hardware spec name for billing (e.g., 'a100-80gb', 'cpu_core')
    """
    try:
        spec_dict = _get_model_spec(model_slug)

        # Determine hardware spec based on resource requirements
        gpu_type = spec_dict.get("gpu")
        if gpu_type:
            # Return GPU type as-is since it matches MODAL_RESOURCE_BASE_COSTS keys
            return gpu_type
        else:
            # CPU-only model - use cpu_core as the billing unit
            return "cpu_core"

    except Exception as e:
        print(f"Failed to get hardware spec for {model_slug}: {e}")
        return "a100-80gb"  # Safe fallback
