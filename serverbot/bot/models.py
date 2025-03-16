from django.db import models
from django.contrib.auth.models import User
from django.db.models import TextField


# Create your models here.


class Activity(models.Model):
    name = models.TextField(null=False, blank=False)
    description = models.TextField(null=False, blank=False)

    def __str__(self) -> TextField:
        return self.name


class Program(models.Model):
    name = models.TextField(null=False, blank=False)
    title = models.TextField(null=False, blank=False,
                             default="Untitled program")
    path = models.TextField(null=False, blank=True, unique=True)
    command = models.TextField(null=True, default="None")
    description = models.CharField(max_length=200, null=True, default="None")
    # activity = models.ForeignKey(Activity, on_delete=models.DO_NOTHING, null=False)
    # hidden fields
    id = models.BigAutoField(primary_key=True)  # ID único y autoincremental
    is_running = models.BooleanField(default=False)

    def is_equal(self, comparator):
        return str(self.name).lower() == str(comparator['name']).lower() and self.title == comparator['title'] and self.path == comparator['path'] and self.command == comparator.get('command', 'None') and self.description == comparator.get('description', 'None')


class Room(models.Model):  # One room can have multiple messages
    host = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=200)
    # It can be blank because null=True
    description = models.TextField(null=True, blank=True)
    # this creates a many-to-many relationship in the database
    participants = models.ManyToManyField(
        User, related_name='participants', blank=True)
    # It refreshes with the system time
    updated = models.DateTimeField(auto_now=True)
    # It refreshes the time only when its created
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        # '-updated' for inverse ordering, and 'updated' for normal ordering
        ordering = ['-updated', '-created']

    def __str__(self):
        return self.name


class Message(models.Model):  # One message can have only one room and user
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # CASCADE deletes all messages if the room is deleted
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    body = models.TextField()
    # It refreshes with the system time
    updated = models.DateTimeField(auto_now=True)
    # It refreshes the time only when its created
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        # '-updated' for inverse ordering, and 'updated' for normal ordering
        ordering = ['-updated', '-created']

    def __str__(self):
        return self.body[0:50]
