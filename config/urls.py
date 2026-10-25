"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from web_sem.nlp.views import questions
from web_sem.views import home

urlpatterns = [
    path('', home, name='home'),
    path('questions/', questions, name='questions'),
    path('personnes/', include('personne.urls')),
    path('sources/', include('source_production.urls')),
    path('stockages/', include('stockage.urls')),
    path('consommateurs/', include('consommateur.urls')),
    path('contrats/', include('contrat.urls')),
    path('zones/', include('zone.urls')),
    path('admin/', admin.site.urls),
]
