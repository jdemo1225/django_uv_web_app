import logging

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import Task

logger = logging.getLogger(__name__)

_notifier = None


def _get_notifier():
    global _notifier
    if _notifier is None:
        from .services import WebhookNotifier
        _notifier = WebhookNotifier()
    return _notifier


@receiver(post_save, sender=Task)
def task_saved(sender, instance, created, **kwargs):
    notifier = _get_notifier()
    if created:
        logger.info("task created: %s (id=%d)", instance.title, instance.id)
        notifier.on_created(instance)
    else:
        logger.info("task updated: %s (id=%d)", instance.title, instance.id)
        notifier.on_updated(instance)


@receiver(pre_delete, sender=Task)
def task_deleting(sender, instance, **kwargs):
    logger.info("task deleting: %s (id=%d)", instance.title, instance.id)
    _get_notifier().on_deleted(instance)
