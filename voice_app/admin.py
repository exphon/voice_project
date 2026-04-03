from django.contrib import admin
from .models import AudioRecord

# Storytelling \ud0c0\uc785 \ud544\ud130
class StorytellingTypeFilter(admin.SimpleListFilter):
    title = 'Storytelling \ud0c0\uc785'
    parameter_name = 'storytelling_type'
    
    def lookups(self, request, model_admin):
        return (
            ('storytelling_required', '\uc790\ubc1c\ud654 \ud544\uc218\uc9c8\ubb38 (\ud558\ub8e8 \uc77c\uacfc)'),
            ('storytelling_additional', '\uc790\ubc1c\ud654 \ucd94\uac00\uc9c8\ubb38 (\ud589\ubcf5\ud55c \uc21c\uac04)'),
            ('all_storytelling', '\ubaa8\ub4e0 Storytelling'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'storytelling_required':
            return queryset.filter(
                category='senior',
                category_specific_data__task_type='storytelling_required'
            )
        elif self.value() == 'storytelling_additional':
            return queryset.filter(
                category='senior',
                category_specific_data__task_type='storytelling_additional'
            )
        elif self.value() == 'all_storytelling':
            return queryset.filter(
                category='senior',
                category_specific_data__task_type__in=['storytelling_required', 'storytelling_additional']
            )

# Register your models here.
@admin.register(AudioRecord)
class AudioRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'identifier', 'audio_file', 'category', 'get_task_type', 'gender', 'age', 'status', 'created_at')
    list_filter = ('category', 'status', 'gender', StorytellingTypeFilter, 'created_at')
    search_fields = ('identifier', 'audio_file', 'transcript', 'manual_transcript', 'category')
    readonly_fields = ('created_at',)
    
    def get_task_type(self, obj):
        """\uacfc\uc81c \uc720\ud615 \ud45c\uc2dc"""
        if obj.category_specific_data:
            task_type = obj.category_specific_data.get('task_type', '')
            if task_type == 'storytelling_required':
                return '\ud544\uc218\uc9c8\ubb38'
            elif task_type == 'storytelling_additional':
                return '\ucd94\uac00\uc9c8\ubb38'
            return task_type
        return '-'
    get_task_type.short_description = '\uacfc\uc81c \uc720\ud615'

