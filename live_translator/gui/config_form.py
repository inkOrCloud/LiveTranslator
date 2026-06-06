"""Dynamic configuration form builder driven by JSON Schema."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QWidget,
)


class ConfigFormBuilder:
    """Builds a Qt form from a JSON Schema.

    Example::

        schema = DeepLTranslateService.config_schema()
        builder = ConfigFormBuilder(schema, current_config)
        form_widget = builder.build()
        updated = builder.get_values()
    """

    def __init__(
        self, schema: dict[str, Any], current_values: dict[str, Any] | None = None
    ) -> None:
        """Initialize the form builder.

        Args:
            schema: JSON Schema dict with ``properties`` key.
            current_values: Optional dict of existing values to populate.
        """
        self._schema = schema
        self._values = current_values or {}
        self._widgets: dict[str, QWidget] = {}
        self._widget: QGroupBox | None = None

    def build(self) -> QGroupBox:
        """Build the form widget.

        Returns:
            A QGroupBox containing the dynamically generated form.
        """
        title = self._schema.get("title", "Configuration")
        group = QGroupBox(title)
        layout = QFormLayout(group)

        properties = self._schema.get("properties", {})
        for key, prop_schema in properties.items():
            widget = self._create_widget(key, prop_schema)
            self._widgets[key] = widget
            label = prop_schema.get("title", key)
            layout.addRow(label, widget)

        self._widget = group
        return group

    def _create_widget(self, key: str, prop_schema: dict[str, Any]) -> QWidget:
        """Create a single widget for a schema property.

        Args:
            key: Property name.
            prop_schema: Property's JSON Schema sub-dict.

        Returns:
            The created QWidget.
        """
        prop_type = prop_schema.get("type", "string")
        fmt = prop_schema.get("format", "")
        default = prop_schema.get("default")
        current = self._values.get(key, default)
        description = prop_schema.get("description", "")

        if prop_type == "string" and fmt == "password":
            widget = QLineEdit()
            widget.setEchoMode(QLineEdit.EchoMode.Password)
            if current:
                widget.setText(str(current))
            widget.setToolTip(description)
            return widget

        if prop_type == "string" and "enum" in prop_schema:
            widget = QComboBox()
            for option in prop_schema["enum"]:
                widget.addItem(str(option), option)
            if current:
                idx = widget.findData(current)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            widget.setToolTip(description)
            return widget

        if prop_type == "boolean":
            widget = QCheckBox()
            if isinstance(current, bool):
                widget.setChecked(current)
            widget.setToolTip(description)
            return widget

        if prop_type == "integer":
            widget = QSpinBox()
            if "default" in prop_schema:
                widget.setValue(int(prop_schema["default"]))
            if "minimum" in prop_schema:
                widget.setMinimum(int(prop_schema["minimum"]))
            if "maximum" in prop_schema:
                widget.setMaximum(int(prop_schema["maximum"]))
            if isinstance(current, (int, float)):
                widget.setValue(int(current))
            widget.setToolTip(description)
            return widget

        if prop_type == "number":
            widget = QDoubleSpinBox()
            if "default" in prop_schema:
                widget.setValue(float(prop_schema["default"]))
            if "minimum" in prop_schema:
                widget.setMinimum(float(prop_schema["minimum"]))
            if "maximum" in prop_schema:
                widget.setMaximum(float(prop_schema["maximum"]))
            if isinstance(current, (int, float)):
                widget.setValue(float(current))
            widget.setToolTip(description)
            return widget

        widget = QLineEdit()
        if current:
            widget.setText(str(current))
        widget.setToolTip(description)
        return widget

    def get_widget(self, key: str) -> QWidget | None:
        """Get the widget for a property key.

        Args:
            key: Property name.

        Returns:
            The widget, or None if not found.
        """
        return self._widgets.get(key)

    def get_values(self) -> dict[str, Any]:
        """Collect current values from all widgets.

        Returns:
            Dict mapping property names to their current widget values.
        """
        values: dict[str, Any] = {}

        for key, widget in self._widgets.items():
            values[key] = self._read_widget(widget)

        return values

    @staticmethod
    def _read_widget(widget: QWidget) -> Any:
        """Read the value from a widget.

        Args:
            widget: The widget to read.

        Returns:
            The widget's value in the correct Python type.
        """
        if isinstance(widget, QLineEdit):
            return widget.text()

        if isinstance(widget, QComboBox):
            return widget.currentData()

        if isinstance(widget, QCheckBox):
            return widget.isChecked()

        if isinstance(widget, QSpinBox):
            return widget.value()

        if isinstance(widget, QDoubleSpinBox):
            return widget.value()

        return ""
