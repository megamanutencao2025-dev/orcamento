from django.contrib import admin

from .models import AnaliseProdutividade, ItemExecutado

admin.site.register([AnaliseProdutividade, ItemExecutado])
