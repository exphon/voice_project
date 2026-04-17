from django.urls import path

from .views import ddk_analysis, help_periodicity, index, sustained_vowel_analysis


app_name = "voice_analysis"

urlpatterns = [
    path("", index, name="index"),
    path("sustained-vowel/", sustained_vowel_analysis, name="sustained_vowel_analysis"),
    path("ddk/", ddk_analysis, name="ddk_analysis"),
    path("help/periodicity/", help_periodicity, name="help_periodicity"),
]