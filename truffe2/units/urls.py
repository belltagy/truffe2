# -*- coding: utf-8 -*-

from django.conf.urls import patterns, url


urlpatterns = patterns(
    'units.views',

    url(r'^accreds/$', 'accreds_list'),
    url(r'^accreds/json$', 'accreds_list_json'),
    url(r'^accreds/logs/$', 'accreds_logs_list'),
    url(r'^accreds/logs/json$', 'accreds_logs_list_json'),
    url(r'^accreds/(?P<pk>[0-9,]+)/renew$', 'accreds_renew'),
    url(r'^accreds/(?P<pk>[0-9~]+)/edit$', 'accreds_edit'),
    url(r'^accreds/(?P<pk>[0-9,]+)/delete$', 'accreds_delete'),
    url(r'^accreds/(?P<pk>[0-9,]+)/validate$', 'accreds_validate'),
    url(r'^accreds/add$', 'accreds_add'),

    url(r'^role/(?P<pk>\d*)/users$', 'role_userslist'),
)
