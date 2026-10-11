from django import forms

INPUT_CLASS = (
    "block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm "
    "focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200 "
    "disabled:bg-slate-100 disabled:text-slate-500"
)
CHECKBOX_CLASS = "h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"


class StyledFormMixin:
    """Memberi kelas Tailwind pada semua widget. Taruh di urutan pertama pewarisan."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            css = CHECKBOX_CLASS if isinstance(widget, forms.CheckboxInput) else INPUT_CLASS
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()
