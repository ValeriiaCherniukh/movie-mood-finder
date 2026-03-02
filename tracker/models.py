from django.conf import settings
from django.db import models


class Title(models.Model):
    tmdb_id = models.IntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    poster_path = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return self.name


class UserTitle(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Заплановано"
        WATCHING = "watching", "Дивлюсь зараз"
        WATCHED = "watched", "Переглянуто"
        LIKED = "liked", "Сподобалось"
        DISLIKED = "disliked", "Не сподобалось"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.ForeignKey(Title, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "title")

    def __str__(self):
        return f"{self.user} → {self.title} ({self.status})"
