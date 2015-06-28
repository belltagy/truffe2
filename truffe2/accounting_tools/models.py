# -*- coding: utf-8 -*-

from django import forms
from django.db import models
from django.utils.translation import ugettext_lazy as _


from generic.models import GenericModel, GenericStateModel, FalseFK, GenericContactableModel
from rights.utils import UnitExternalEditableModel
from accounting_core.utils import AccountingYearLinked
from app.utils import get_current_year


class _Subvention(GenericModel, AccountingYearLinked, GenericStateModel, UnitExternalEditableModel, GenericContactableModel):

    SUBVENTION_TYPE = (
        ('subvention', _(u'Subvention')),
        ('sponsorship', _(u'Sponsoring')),
        )

    class MetaRightsUnit(UnitExternalEditableModel.MetaRightsUnit):
        access = 'TRESORERIE'
        world_ro_access = True

    name = models.CharField(_(u'Nom du projet'), max_length=255)
    amount_asked = models.SmallIntegerField(_(u'Montant demandé'))
    amount_given = models.SmallIntegerField(_(u'Montant attribué'))
    mobility_asked = models.SmallIntegerField(_(u'Montant mobilité demandé'), blank=True)
    mobility_given = models.SmallIntegerField(_(u'Montant mobilité attribué'), blank=True)
    unit = FalseFK('units.models.Unit', verbose_name=_(u'Association / Commission'))
    description = models.TextField(_('Description'), blank=True, null=True)
    comment_root = models.TextField(_('Commentaire AGEPoly'), blank=True, null=True)
    kind = models.CharField(_(u'Type de soutien'), max_length=15, choices=SUBVENTION_TYPE, blank=True)

    class Meta:
        abstract = True
        unique_together = (("unit", "accounting_year"),)

    class MetaData:
        list_display = [
            ('name', _(u'Projet')),
            ('unit', _(u'Association / Commission')),
            ('amount_asked', _(u'Montant demandé')),
        ]

        default_sort = "[2, 'asc']"  # unit
        filter_fields = ('name', 'kind', 'unit')

        details_display = list_display + [('description', _(u'Description')), ('accounting_year', _(u'Année comptable'))]
        extra_right_display = {'comment_root': lambda (obj, user): obj.rights_can('LIST', user)}

        base_title = _(u'Subvention')
        list_title = _(u'Liste des demandes de subvention')
        base_icon = 'fa fa-list'
        elem_icon = 'fa fa-smile-o'

        menu_id = 'menu-compta-subventions'

        help_list = _(u"""Les demandes de subvention peuvent être faites par toutes les commissions ou association auprès de l'AGEPoly.""")

    class MetaAccounting:
        copiable = False

    class MetaState:

        states = {
            '0_draft': _(u'Brouillon'),
            '1_submited': _(u'Demande soumise'),
            '2_treated': _(u'Demande traitée'),
        }

        default = '0_draft'

        states_texts = {
            '0_draft': _(u'La demande est en cours de création et n\'est pas publique.'),
            '1_submited': _(u'La demande a été soumise.'),
            '2_treated': _(u'La demande a été traitée.'),
        }

        states_links = {
            '0_draft': ['1_submited'],
            '1_submited': ['2_treated'],
            '2_treated': [],
        }

        states_colors = {
            '0_draft': 'primary',
            '1_submited': 'default',
            '2_treated': 'success',
        }

        states_icons = {
            '0_draft': '',
            '1_submited': '',
            '2_treated': '',
            '3_archived': '',
        }

        list_quick_switch = {
            '0_draft': [('1_submited', 'fa fa-check', _(u'Soumettre la demande')), ],
            '1_submited': [('2_treated', 'fa fa-check', _(u'Marquer la demande comme traitée')), ],
            '2_treated': [],
        }

        states_default_filter = '0_draft,1_submited,2_treated'
        states_default_filter_related = '0_draft,1_submited,2_treated'
        status_col_id = 3

    def may_switch_to(self, user, dest_state):

        return self.rights_can('EDIT', user)

    def can_switch_to(self, user, dest_state):

        if self.status == '2_treated' and not user.is_superuser:
            return (False, _(u'Seul un super utilisateur peut sortir cet élément de l\'état traité'))

        if int(dest_state[0]) - int(self.status[0]) != 1 and not user.is_superuser:
            return (False, _(u'Seul un super utilisateur peut sauter des étapes ou revenir en arrière.'))

        if self.status == '1_submited' and not self.rights_in_root_unit(user, self.MetaRightsUnit.access):
            return (False, _(u'Seul un membre du Comité de Direction peut marquer la demande comme traitée.'))

        if not self.rights_can('EDIT', user):
            return (False, _('Pas les droits.'))

        return super(_Subvention, self).can_switch_to(user, dest_state)

    def __unicode__(self):
        return u"{} {}".format(self.unit, self.accounting_year)

    def genericFormExtraClean(self, data, form):
        """Check that unique_together is fulfiled"""
        from accounting_core.models import Subvention

        if Subvention.objects.exclude(pk=self.pk).filter(accounting_year=get_current_year(form.truffe_request), unit__name=data['unit']).count():
            raise forms.ValidationError(_(u'Une demande de subvention pour cette unité existe déjà pour cette année comptable.'))  # Potentiellement parmi les supprimées

    def rights_can_LIST(self, user):
        # Seul le comité de direction peut lister les demandes
        return self.rights_in_root_unit(user, self.MetaRightsUnit.access)


class SubventionLine(models.Model):
    name = models.CharField(_(u'Nom de l\'évènement'), max_length=255)
    start_date = models.DateField(_(u'Début de l\'évènement'))
    end_date = models.DateField(_(u'Fin de l\'évènement'))
    place = models.CharField(_(u'Lieu de l\'évènement'), max_length=100)
    nb_spec = models.SmallIntegerField(_(u'Nombre de personnes attendues'))

    subvention = FalseFK('Subvention', verbose_name=_(u'Subvention/sponsoring'))
