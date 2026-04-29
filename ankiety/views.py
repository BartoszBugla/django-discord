from django.shortcuts import render, get_object_or_404
from .models import Pytanie


def index(request):
    return render(request, "ankiety/index.html")


def szczegoly(request, pytanie_id):
    pytanie = get_object_or_404(Pytanie, pk=pytanie_id)
    return render(request, "ankiety/szczegoly.html", {"pytanie": pytanie})
