"""
Tests for billing service initialization and mixin usage.

These tests ensure that:
1. BillingService accepts all expected parameters (including resource_metadata)
2. Billing mixins can initialize billing correctly
3. resource_metadata is properly passed and stored
4. Common usage patterns (like in model app.py files) work correctly
"""

import inspect
from unittest.mock import MagicMock, patch

from models.commons.billing.mixin import (
    BillingMixin,
    BillingMixinBase,
    BillingMixinSnap,
)
from models.commons.billing.service import BillingService


class TestBillingServiceInitialization:
    """Test BillingService initialization with various parameter combinations."""

    def test_init_with_all_parameters(self):
        """Test that BillingService accepts all expected parameters."""
        service = BillingService(
            app_name="test_app",
            class_name="TestClass",
            username="test_user",
            resource_metadata={"gpu": "A100", "memory": "40GB"},
        )

        assert service.app_name == "test_app"
        assert service.class_name == "TestClass"
        assert service.username == "test_user"
        assert service.resource_metadata == {"gpu": "A100", "memory": "40GB"}

    def test_init_without_resource_metadata(self):
        """Test that resource_metadata defaults to empty dict."""
        service = BillingService(
            app_name="test_app",
            class_name="TestClass",
            username="test_user",
        )

        assert service.resource_metadata == {}

    def test_init_with_none_resource_metadata(self):
        """Test that None resource_metadata becomes empty dict."""
        service = BillingService(
            app_name="test_app",
            class_name="TestClass",
            username="test_user",
            resource_metadata=None,
        )

        assert service.resource_metadata == {}

    def test_init_signature_matches_usage(self):
        """Test that __init__ signature accepts all parameters used in mixin."""
        # Get the signature of BillingService.__init__
        init_sig = inspect.signature(BillingService.__init__)
        init_params = set(init_sig.parameters.keys()) - {"self"}

        # Parameters that mixin passes to BillingService
        expected_params = {"app_name", "class_name", "username", "resource_metadata"}

        assert expected_params.issubset(
            init_params
        ), f"BillingService.__init__ missing parameters. Expected: {expected_params}, Got: {init_params}"


class TestBillingMixinBase:
    """Test BillingMixinBase _billing_enter and _billing_exit methods."""

    def test_billing_enter_with_resource_metadata_argument(self):
        """Test _billing_enter with resource_metadata passed as argument."""

        # Create a mock class that inherits from BillingMixinBase
        class TestModel(BillingMixinBase):
            app_username = "test_user"

            def _get_app_name_from_module(self):
                return "test_app"

        model = TestModel()

        # Mock the module to have app_name
        with patch.object(
            inspect, "getmodule", return_value=MagicMock(app_name="test_app")
        ):
            with patch(
                "models.commons.billing.service.initialize_redis_client",
                return_value=(None, False),
            ):
                # Mock start_billing to avoid actual thread creation
                with patch.object(BillingService, "start_billing", return_value=True):
                    model._billing_enter(resource_metadata={"gpu": "A100"})

        # Verify billing service was created with resource_metadata
        assert hasattr(model, "billing_service")
        assert model.billing_service.resource_metadata == {"gpu": "A100"}

    def test_billing_enter_with_resource_metadata_from_instance(self):
        """Test _billing_enter when resource_metadata comes from instance attribute."""

        class TestModel(BillingMixinBase):
            app_username = "test_user"
            resource_metadata = {"gpu": "A100", "memory": "40GB"}

            def _get_app_name_from_module(self):
                return "test_app"

        model = TestModel()

        with patch.object(
            inspect, "getmodule", return_value=MagicMock(app_name="test_app")
        ):
            with patch(
                "models.commons.billing.service.initialize_redis_client",
                return_value=(None, False),
            ):
                with patch.object(BillingService, "start_billing", return_value=True):
                    model._billing_enter()  # No argument, should use instance attribute

        assert hasattr(model, "billing_service")
        assert model.billing_service.resource_metadata == {
            "gpu": "A100",
            "memory": "40GB",
        }

    def test_billing_enter_with_no_resource_metadata(self):
        """Test _billing_enter when no resource_metadata is available."""

        class TestModel(BillingMixinBase):
            app_username = "test_user"

            def _get_app_name_from_module(self):
                return "test_app"

        model = TestModel()

        with patch.object(
            inspect, "getmodule", return_value=MagicMock(app_name="test_app")
        ):
            with patch(
                "models.commons.billing.service.initialize_redis_client",
                return_value=(None, False),
            ):
                with patch.object(BillingService, "start_billing", return_value=True):
                    model._billing_enter()

        assert hasattr(model, "billing_service")
        assert model.billing_service.resource_metadata == {}

    def test_billing_enter_argument_overrides_instance_attribute(self):
        """Test that resource_metadata argument overrides instance attribute."""

        class TestModel(BillingMixinBase):
            app_username = "test_user"
            resource_metadata = {"gpu": "V100"}  # Instance attribute

            def _get_app_name_from_module(self):
                return "test_app"

        model = TestModel()

        with patch.object(
            inspect, "getmodule", return_value=MagicMock(app_name="test_app")
        ):
            with patch(
                "models.commons.billing.service.initialize_redis_client",
                return_value=(None, False),
            ):
                with patch.object(BillingService, "start_billing", return_value=True):
                    # Pass different metadata as argument
                    model._billing_enter(resource_metadata={"gpu": "A100"})

        assert model.billing_service.resource_metadata == {
            "gpu": "A100"
        }  # Argument wins

    def test_billing_exit_cleans_up(self):
        """Test that _billing_exit properly stops billing service."""

        class TestModel(BillingMixinBase):
            app_username = "test_user"

            def _get_app_name_from_module(self):
                return "test_app"

        model = TestModel()

        with patch.object(
            inspect, "getmodule", return_value=MagicMock(app_name="test_app")
        ):
            with patch(
                "models.commons.billing.service.initialize_redis_client",
                return_value=(None, False),
            ):
                with patch.object(BillingService, "start_billing", return_value=True):
                    model._billing_enter()

                # Mock stop_billing
                with patch.object(BillingService, "stop_billing") as mock_stop:
                    model._billing_exit(cleanup_other_threads=False)
                    mock_stop.assert_called_once()


class TestBillingMixinSnap:
    """Test BillingMixinSnap which extends BillingMixin."""

    def test_billing_mixin_snap_inherits_from_billing_mixin(self):
        """Test that BillingMixinSnap properly inherits from BillingMixin."""
        assert issubclass(BillingMixinSnap, BillingMixin)
        assert issubclass(BillingMixinSnap, BillingMixinBase)

    def test_billing_mixin_snap_has_save_snapshot_uptime(self):
        """Test that BillingMixinSnap has save_snapshot_uptime method."""
        assert hasattr(BillingMixinSnap, "save_snapshot_uptime")


class TestCommonUsagePatterns:
    """Test common usage patterns found in model app.py files."""

    def test_pattern_with_resource_metadata_attribute(self):
        """Test the pattern: self.resource_metadata = {...}; self._billing_enter(resource_metadata=self.resource_metadata)"""

        class TestModel(BillingMixinBase):
            app_username = "test_user"

            def _get_app_name_from_module(self):
                return "test_app"

            def setup(self):
                # Common pattern in app.py files
                self.resource_metadata = {
                    "gpu": "A100",
                    "memory": "40GB",
                    "cpu": 4,
                }
                self._billing_enter(resource_metadata=self.resource_metadata)

        model = TestModel()

        with patch.object(
            inspect, "getmodule", return_value=MagicMock(app_name="test_app")
        ):
            with patch(
                "models.commons.billing.service.initialize_redis_client",
                return_value=(None, False),
            ):
                with patch.object(BillingService, "start_billing", return_value=True):
                    model.setup()

        assert model.billing_service.resource_metadata == {
            "gpu": "A100",
            "memory": "40GB",
            "cpu": 4,
        }

    def test_pattern_without_explicit_resource_metadata(self):
        """Test the pattern: self._billing_enter() without explicit resource_metadata."""

        class TestModel(BillingMixinBase):
            app_username = "test_user"

            def _get_app_name_from_module(self):
                return "test_app"

            def setup(self):
                # Pattern where resource_metadata might not be set
                self._billing_enter()

        model = TestModel()

        with patch.object(
            inspect, "getmodule", return_value=MagicMock(app_name="test_app")
        ):
            with patch(
                "models.commons.billing.service.initialize_redis_client",
                return_value=(None, False),
            ):
                with patch.object(BillingService, "start_billing", return_value=True):
                    model.setup()

        # Should work without error and have empty dict
        assert hasattr(model, "billing_service")
        assert model.billing_service.resource_metadata == {}


class TestParameterCompatibility:
    """Test that parameter passing is compatible between mixin and service."""

    def test_all_parameters_can_be_passed(self):
        """Test that all parameters mixin collects can be passed to BillingService."""

        # This test ensures we catch signature mismatches early
        class TestModel(BillingMixinBase):
            app_username = "test_user"

            def _get_app_name_from_module(self):
                return "test_app"

        model = TestModel()

        # Collect parameters as mixin does
        app_name = "test_app"
        class_name = model.__class__.__name__
        username = getattr(model, "app_username", "default_user")
        resource_metadata = getattr(model, "resource_metadata", {})

        # Verify we can instantiate BillingService with these exact parameters
        # This would fail if signature doesn't match
        service = BillingService(
            app_name=app_name,
            class_name=class_name,
            username=username,
            resource_metadata=resource_metadata,
        )

        assert service.app_name == app_name
        assert service.class_name == class_name
        assert service.username == username
        assert service.resource_metadata == resource_metadata
