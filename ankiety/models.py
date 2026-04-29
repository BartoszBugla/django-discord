from django.db import models


class Pytanie(models.Model):
    tresc = models.CharField(max_length=200)
    data_publikacji = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.tresc
