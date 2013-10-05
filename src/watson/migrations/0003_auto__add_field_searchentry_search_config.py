# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'SearchEntry.search_config'
        db.add_column('watson_searchentry', 'search_config',
                      self.gf('django.db.models.fields.CharField')(default='english', max_length=24),
                      keep_default=False)

    def backwards(self, orm):
        # Deleting field 'SearchEntry.search_config'
        db.delete_column('watson_searchentry', 'search_config')

    models = {
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'watson.searchentry': {
            'Meta': {'object_name': 'SearchEntry'},
            'content': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'engine_slug': ('django.db.models.fields.CharField', [], {'default': "'default'", 'max_length': '200', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meta_encoded': ('django.db.models.fields.TextField', [], {}),
            'object_id': ('django.db.models.fields.TextField', [], {}),
            'object_id_int': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'search_config': ('django.db.models.fields.CharField', [], {'default': "'english'", 'max_length': '24'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '1000'}),
            'url': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'blank': 'True'})
        }
    }

    complete_apps = ['watson']