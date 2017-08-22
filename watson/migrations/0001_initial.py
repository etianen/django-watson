# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.core.management import call_command


def install_watson(apps, schema_editor):
    call_command("installwatson", verbosity=0)


def uninstall_watson(apps, schema_editor):
    call_command("uninstallwatson", verbosity=0)


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('engine_slug', models.CharField(default='default', max_length=200, db_index=True)),
                ('object_id', models.TextField()),
                ('object_id_int', models.IntegerField(db_index=True, null=True, blank=True)),
                ('title', models.CharField(max_length=1000)),
                ('description', models.TextField(blank=True)),
                ('content', models.TextField(blank=True)),
                ('url', models.CharField(max_length=1000, blank=True)),
                ('meta_encoded', models.TextField()),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'search entries',
            },
            bases=(models.Model,),
        ),
        migrations.RunPython(
            install_watson,
            uninstall_watson,
        ),
    ]
