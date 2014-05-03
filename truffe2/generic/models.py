# -*- coding: utf-8 -*-

from django.db import models
from django.conf import settings
import inspect
from users.models import TruffeUser
from django.utils.translation import ugettext_lazy as _
import importlib
from django.conf.urls import patterns, url
from generic import views


def build_models_list_of(Class):
    retour = []
    already_returned = []
    for app in settings.INSTALLED_APPS:
        try:
            module = importlib.import_module(app)
            models_module = importlib.import_module('.models', app)
            views_module = importlib.import_module('.views', app)
            urls_module = importlib.import_module('.urls', app)
        except:
            continue

        clsmembers = inspect.getmembers(models_module, inspect.isclass)

        for model_name, model_class in clsmembers:
            if issubclass(model_class, Class) and model_class != Class and model_class not in already_returned:
                retour.append((module, (views_module, urls_module, models_module), model_class))
                already_returned.append(model_class)

    return retour


class GenericModel(models.Model):
    """Un modele generic pour truffe"""

    deleted = models.BooleanField(default=False)

    @staticmethod
    def startup():
        """Execute code at startup"""

        classes = build_models_list_of(GenericModel)

        for module, (views_module, urls_module, models_module), model_class in classes:

            if model_class.__name__[0] != '_':
                continue

            # Create the new model
            extra_data = {'__module__': models_module.__name__}

            if issubclass(model_class, GenericStateModel):
                extra_data.update(GenericStateModel.do(module, models_module, model_class))

            real_model_class = type(model_class.__name__[1:], (model_class,), extra_data)

            setattr(models_module, real_model_class.__name__, real_model_class)

            # Add the logging model
            logging_class = type(real_model_class.__name__ + 'Logging', (GenericLogEntry,), {'object': models.ForeignKey(real_model_class), '__module__': models_module.__name__})
            setattr(models_module, logging_class.__name__, logging_class)

            # Add views
            if not hasattr(views_module, 'x'):
                views_module.x = views.generate_x(real_model_class.__name__.lower(), real_model_class)

                # Add urls to views
                urls_module.urlpatterns += patterns('main.views', url(r'^x$', 'x'))

    class Meta:
        abstract = True


class GenericStateModel():
    """Un modele generic avec une notiion de status"""

    @staticmethod
    def do(module, models_module, model_class):
        """Execute code at startup"""

        return {'status': models.CharField(max_length=255, choices=model_class.MetaState.states.iteritems(), default=model_class.MetaState.default)}


class GenericLogEntry(models.Model):

    when = models.DateTimeField(auto_now_add=True)
    extra_data = models.TextField(blank=True)
    who = models.ForeignKey(TruffeUser)

    LOG_TYPES = (
        ('created', _(u'Creation')),
        ('edited', _(u'Edité')),
        ('deleted', _(u'Supprimé')),
        ('state_changed', _(u'Status changé'))
    )

    what = models.CharField(max_length=64, choices=LOG_TYPES)

    class Meta:
        abstract = True
