# core/site_views.py
from django.shortcuts import render

def home(request):
    return render(request, "site/home.html")
