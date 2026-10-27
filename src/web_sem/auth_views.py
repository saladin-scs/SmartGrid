"""Views for the public authentication flow."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from web_sem.auth_forms import RegistrationForm, SmartGridAuthenticationForm


class SmartGridLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = SmartGridAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form: SmartGridAuthenticationForm) -> HttpResponse:
        response = super().form_valid(form)
        messages.success(self.request, "Connexion réussie.")
        return response


@login_not_required
@require_http_methods(["GET", "POST"])
def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("overview")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Votre compte a été créé. Vous pouvez vous connecter.")
        return redirect("login")

    return render(request, "registration/register.html", {"form": form})


class SmartGridLogoutView(LogoutView):
    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        response = super().post(request, *args, **kwargs)
        messages.success(request, "Vous êtes déconnecté.")
        return response
