from django.urls import reverse


class FormPageMixin:
    """Konteks standar untuk halaman formulir (templates/form.html)."""

    page_title = ""
    submit_label = "Simpan"
    cancel_url_name = None

    def get_page_title(self):
        return self.page_title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.get_page_title()
        context["submit_label"] = self.submit_label
        context["cancel_url"] = reverse(self.cancel_url_name) if self.cancel_url_name else None
        return context
