# -*- coding: utf-8 -*-

from django.shortcuts import get_object_or_404, render, redirect
from django.template import RequestContext
from django.core.context_processors import csrf
from django.views.decorators.csrf import csrf_exempt
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.utils.encoding import smart_str
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from django.contrib.sites.models import get_current_site
from django.http import HttpResponseRedirect
from django.db import connections
from django.core.paginator import InvalidPage, EmptyPage, Paginator, PageNotAnInteger
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now
from django.utils.http import is_safe_url


from users.models import TruffeUser, UserPrivacy
from users.forms import TruffeUserForm, TruffeCreateUserForm, TruffePasswordResetForm
from app.utils import send_templated_mail

import phonenumbers

from generic.datatables import generic_list_json
import re
import os
import time
import requests
import shutil


def login(request, why=None):
    """View to display the login page"""

    if request.user.is_authenticated():
        return redirect('/')

    why = request.GET.get('why') or why

    # Debuging code
    # user = TruffeUser.objects.get(username=request.GET.get('username'))
    # user.backend = 'app.tequila.Backend'
    # auth_login(request, user)

    if request.method == 'POST':
        username = request.POST.get('username')

        if re.match('^\d{6}$', username):
            why = "username_is_sciper"
        else:
            try:
                user = TruffeUser.objects.get(username=username)
                user.backend = 'app.tequila.Backend'
                if user.check_password(request.POST.get('password')):
                    auth_login(request, user)

                    redirect_to = request.GET.get('next', '/')
                    if not is_safe_url(url=redirect_to, host=request.get_host()):
                        redirect_to = '/'
                    return redirect(redirect_to)

            except TruffeUser.DoesNotExist:
                pass

            why = "bad_credentials"

    reset_form = TruffePasswordResetForm()
    return render(request, 'users/login/login.html', {'why': why, 'reset_form': reset_form})


@login_required
def users_list(request):
    """Display the list of users"""

    can_create = TruffeUser.static_rights_can('CREATE', request.user)
    return render(request, 'users/users/list.html', {'can_create': can_create})


@login_required
@csrf_exempt
def users_list_json(request):
    """Json for user list"""

    return generic_list_json(request, TruffeUser, ['username', 'first_name', 'last_name', 'pk', 'pk'], 'users/users/list_json.html')


@login_required
def users_profile(request, pk):
    """Display a user profile"""

    user = get_object_or_404(TruffeUser, pk=pk)

    privacy_values = {}

    for field in UserPrivacy.FIELD_CHOICES:
        privacy_values[field[0]] = UserPrivacy.user_can_access(request.user, user, field[0])

    return render(request, 'users/users/profile.html', {'user_to_display': user, 'privacy_values': privacy_values})


@login_required
def users_edit(request, pk):
    """Edit a user profile"""

    user = get_object_or_404(TruffeUser, pk=pk)

    if not request.user.is_superuser and not user.pk == request.user.pk:
        raise Http404

    if request.method == 'POST':  # If the form has been submitted...
        form = TruffeUserForm(request.user, request.POST, instance=user)

        privacy_values = {}

        for field in UserPrivacy.FIELD_CHOICES:
            privacy_values[field[0]] = request.POST.get('priv_val_' + field[0])

        if form.is_valid():  # If the form is valid
            user = form.save()

            if user.mobile:
                user.mobile = phonenumbers.format_number(phonenumbers.parse(user.mobile, "CH"), phonenumbers.PhoneNumberFormat.E164)
                user.save()

            for (field, value) in privacy_values.iteritems():
                # At this point, the object should exist !
                UserPrivacy.objects.filter(user=user, field=field).update(level=value)

            messages.success(request, _(u'Profil sauvegardé !'))

            return redirect('users.views.users_profile', pk=user.pk)
    else:
        form = TruffeUserForm(request.user, instance=user)

        privacy_values = {}

        for field in UserPrivacy.FIELD_CHOICES:
            privacy_values[field[0]] = UserPrivacy.get_privacy_for_field(user, field[0])

    privacy_choices = UserPrivacy.LEVEL_CHOICES

    return render(request, 'users/users/edit.html', {'form': form, 'privacy_choices': privacy_choices, 'privacy_values': privacy_values})


@login_required
def users_vcard(request, pk):
    """Return a user vcard"""

    user = get_object_or_404(TruffeUser, pk=pk)

    retour = user.generate_vcard(request.user)

    response = HttpResponse(retour, content_type='text/x-vcard')
    nom = smart_str(user.get_full_name())
    nom = nom.replace(' ', '_')
    response['Content-Disposition'] = 'attachment; filename=' + nom + '.vcf'

    return response


@login_required
def users_set_body(request, mode):
    """Set the user mode for the body, keeping it consistent between requests"""

    request.user.body = mode
    request.user.save()

    return HttpResponse('')


@login_required
def users_profile_picture(request, pk):
    """Return a user profile picture"""

    user = get_object_or_404(TruffeUser, pk=pk)

    file_cache = os.path.join(settings.MEDIA_ROOT, 'cache', 'users', str(user.pk) + '.png')

    if not os.path.exists(file_cache) or (os.path.getmtime(file_cache) + 60.0 * 24.0) < time.time():
        if os.path.exists(file_cache):
            os.unlink(file_cache)

        r = requests.get('http://people.epfl.ch/cgi-bin/people/getPhoto?id=' + user.username, stream=True)

        if r.status_code == requests.codes.ok and 'text/html' not in r.headers['content-type']:
            with open(file_cache, 'wb') as fd:
                for chunk in r.iter_content(1024):
                    fd.write(chunk)
        else:
            shutil.copy(os.path.join(settings.MEDIA_ROOT, 'img', 'default_avatar.png'), file_cache)

    return HttpResponseRedirect(settings.MEDIA_URL + '/cache/users/' + str(user.pk) + '.png')

@login_required
def users_create_external(request):
    """Create a new external user"""

    if not TruffeUser.static_rights_can('CREATE', request.user):
        raise Http404

    if request.method == 'POST':
        form = TruffeCreateUserForm(request.POST, request.FILES)

        if form.is_valid():
            password = TruffeUser.objects.make_random_password()

            # Automatically generate username based on firstname and lastname
            firstname = ''.join((char for char in form.cleaned_data['first_name'].lower() if char.isalpha()))
            lastname = ''.join((char for char in form.cleaned_data['last_name'].lower() if char.isalpha()))

            trial = '{}{}'.format(firstname[0], lastname[:8])
            int_trial = ''
            while TruffeUser.objects.filter(username='{}{}'.format(trial, int_trial)).count():
                if int_trial:
                    int_trial += 1
                else:
                    int_trial = 1

            user = TruffeUser.objects.create_user('{}{}'.format(trial, int_trial), password=password, **form.cleaned_data)
            send_templated_mail(request, _('Truffe :: Nouveau compte'), 'nobody@truffe.agepoly.ch', [user.email], 'users/users/mail/newuser', {'psw': password, 'domain': get_current_site(request).name})
            return redirect('users.views.users_list')

    else:
        form = TruffeCreateUserForm()
    return render(request, 'users/users/create_external.html', {'form': form})



@login_required
def password_change_check(request):
    """Check that user has no sciper before allowing to change password"""
    if request.user.username_is_sciper:
        return redirect('users.views.users_profile', pk=request.user.pk)
    return redirect('password_change')


@login_required
def password_change_done(request):
    """Display validation message after changing password"""
    messages.success(request, _(u'Profil sauvegardé !'))
    return redirect('users.views.users_profile', pk=request.user.pk)
