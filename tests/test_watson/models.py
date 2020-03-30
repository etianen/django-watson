import uuid
from django.db import models
from django.utils.encoding import force_str


class TestModelBase(models.Model):
    title = models.CharField(
        max_length=200,
    )

    content = models.TextField(
        blank=True,
    )

    description = models.TextField(
        blank=True,
    )

    is_published = models.BooleanField(
        default=True,
    )

    def __str__(self):
        return force_str(self.title)

    class Meta:
        abstract = True


class WatsonTestModel1(TestModelBase):

    pass


str_pk_gen = 0


def get_str_pk():
    global str_pk_gen
    str_pk_gen += 1
    return str(str_pk_gen)


class WatsonTestModel2(TestModelBase):

    id = models.CharField(
        primary_key=True,
        max_length=100,
        default=get_str_pk
    )


class WatsonTestModel3(TestModelBase):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
    )
