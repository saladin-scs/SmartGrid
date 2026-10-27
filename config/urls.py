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
from django.contrib.auth.decorators import login_not_required
from django.urls import include, path

from web_sem.auth_views import SmartGridLoginView, SmartGridLogoutView, register
from web_sem.nlp.views import create_entity, questions
from web_sem.views import (
    graph_data,
    graph_explorer,
    home,
    overview,
    scenario_list,
    scenario_run,
)

urlpatterns = [
    path(
        'accounts/login/',
        login_not_required(SmartGridLoginView.as_view()),
        name='login',
    ),
    path('accounts/register/', register, name='register'),
    path('accounts/logout/', SmartGridLogoutView.as_view(), name='logout'),
    path('', home, name='home'),
    path('workspace/', overview, name='overview'),
    path('graph/', graph_explorer, name='graph'),
    path('graph/data/', graph_data, name='graph_data'),
    path('questions/', questions, name='questions'),
    path('creation/', create_entity, name='entity_creation'),
    path('scenarios/', scenario_list, name='scenarios'),
    path('scenarios/<slug:key>/', scenario_run, name='scenario_run'),
    path('personnes/', include('personne.urls')),
    path('sources/', include('source_production.urls')),
    path('stockages/', include('stockage.urls')),
    path('consommateurs/', include('consommateur.urls')),
    path('contrats/', include('contrat.urls')),
    path('infrastructures/', include('infrastructure.urls')),
    path('transports/', include('transport.urls')),
    path('zones/', include('zone.urls')),
    path('evenements/', include('evenement.urls')),
    path('capteurs/', include('capteur_dispositif.urls')),
    path('admin/', admin.site.urls),
]
