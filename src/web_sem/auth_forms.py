"""Forms for Django's built-in user authentication."""

from __future__ import annotations

from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


class SmartGridAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "control", "autocomplete": "username", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "control", "autocomplete": "current-password"}
        )


class RegistrationForm(UserCreationForm):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "control", "autocomplete": "username"}
        )
        self.fields["password1"].widget.attrs.update(
            {"class": "control", "autocomplete": "new-password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": "control", "autocomplete": "new-password"}
        )
