# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
from django.core.management import call_command

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'SearchEntry'
        db.create_table('watson_searchentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('object_id', self.gf('django.db.models.fields.TextField')()),
            ('object_id_int', self.gf('django.db.models.fields.IntegerField')(db_index=True, null=True, blank=True)),
            ('search_text', self.gf('django.db.models.fields.TextField')()),
            ('meta_encoded', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('watson', ['SearchEntry'])
        
        # Install the django-watson search indices.
        call_command("installwatson")


    def backwards(self, orm):
        
        # Deleting model 'SearchEntry'
        db.delete_table('watson_searchentry')


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
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meta_encoded': ('django.db.models.fields.TextField', [], {}),
            'object_id': ('django.db.models.fields.TextField', [], {}),
            'object_id_int': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'search_text': ('django.db.models.fields.TextField', [], {})
        }
    }

    complete_apps = ['watson']
