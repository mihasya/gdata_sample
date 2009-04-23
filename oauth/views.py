# Create your views here.
from django.conf import settings #import the project settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext

from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from django.contrib.auth.decorators import login_required

from models import GoogleAccount

import gdata.auth
import gdata.base.service
import gdata.calendar.service
import gdata.contacts.service

import cPickle as Pickle

def index(r):
    if (r.user.is_authenticated()):
        return home(r)
    else:
        return splash(r)

def splash(request):
    if (request.method == 'POST'):
        if (request.POST.has_key('signup')):
            if not (settings.DEBUG):
                request.userequest.message_set.create(message="Signup is currently unavailable")
                return HttpResponseRedirect('/')
            signup_form = UserCreationForm(data=request.POST)
            login_form = AuthenticationForm()
            if (signup_form.is_valid()):
                user = signup_form.save()
                #log the uesr in
                user = authenticate(
                        username=signup_form.cleaned_data['username'],
                        password=signup_form.cleaned_data['password1'])
                login(request, user)
                return home(request)
        elif (request.POST.has_key('login')):
            signup_form = UserCreationForm()
            login_form = AuthenticationForm(data=request.POST)
            if (login_form.is_valid()):
                user = authenticate(
                        username=login_form.cleaned_data['username'], 
                        password=login_form.cleaned_data['password'])
                login(request, user)
                return home(request)
    else:
        signup_form = UserCreationForm()
        login_form = AuthenticationForm()
    params = {
        'signup_form': signup_form,
        'login_form': login_form,
        'debug': settings.DEBUG
    }
    return render_to_response('splash.html', params, 
                                    context_instance=RequestContext(request))


@login_required
def home(request):
    token_search = GoogleAccount.objects.filter(user = request.user)\
        .order_by('-ctime')
    if token_search:
        token_db_object = token_search[0]
        token = Pickle.loads(str(token_db_object.data))
        client = gdata.contacts.service.ContactsService()

        client.SetOAuthInputParameters(
            gdata.auth.OAuthSignatureMethod.RSA_SHA1,
            settings.GDATA_CREDS['key'], 
            consumer_secret=settings.GDATA_CREDS['secret'],
            rsa_key=settings.GDATA_CREDS['rsa_key']
        )
        token.oauth_input_params = client._oauth_input_params
        client.SetOAuthToken(token)
        feed_uri = 'https://www.google.com'+client.GetFeedUri()\
                +'?start-index=1&max-results=10'
        
        contacts = client.GetContactsFeed(feed_uri)

    else:
        return HttpResponseRedirect('/oauth/add_token')
        
    params = {
               'contacts': contacts,
             }
    return render_to_response('home.html', params, 
                                    context_instance=RequestContext(request))

@login_required
def add_token(request):
    #set the scope to contacts API
    cp_scope = gdata.service.lookup_scopes('cp')

    gd_client = gdata.base.service.GBaseService()
    gd_client.SetOAuthInputParameters(
        gdata.auth.OAuthSignatureMethod.RSA_SHA1,
        settings.GDATA_CREDS['key'], 
        consumer_secret=settings.GDATA_CREDS['secret'],
        rsa_key=settings.GDATA_CREDS['rsa_key']
    )
    goog_url = ''
    if not (request.GET.has_key('oauth_token')): #we don't have a token yet
        #create a request token with the contacts api scope
        rt = gd_client.FetchOAuthRequestToken(
            scopes=cp_scope
        )
        #store the token's secret in a session variable
        request.session['token_secret'] = rt.secret
        
        #get an authorization URL for our token from gdata
        gd_client.SetOAuthToken(rt)
        goog_url = gd_client.GenerateOAuthAuthorizationURL()\
                                +'&oauth_callback='+request.build_absolute_uri()
        params = {
            'goog_url': goog_url,
        }

        return render_to_response('add_token.html', params, 
                                        context_instance=RequestContext(request))

        
    else: #we've been redirected back by google with the auth token as a query parameter
        #create a request token object from the URL (converts the query param into a token object)
        rt = gdata.auth.OAuthTokenFromUrl(url=request.build_absolute_uri())
        #set the secret to what we saved above, before we went to Google
        rt.secret = request.session['token_secret']
        #set the scope again
        rt.scopes = cp_scope;
        #upgrade our request token to an access token (where the money at)
        gd_client.UpgradeToOAuthAccessToken(authorized_request_token=rt)
        """this part is confusing: we have to retrieve the authorized access 
        token by doing a lookup I have submitted an issue and a patch to the 
        Python client to make UpgradeToOAuthAccessToken return the authorized 
        token see: 
        http://code.google.com/p/gdata-python-client/issues/detail?id=213"""
        at = gd_client.token_store.find_token(rt.scopes[0])
        """save! how you store the data is arbitrary. I just pickle the token 
        object, though you could probably store the token_key and token_secret 
        individually and reconstruct the object later. (see views.home)"""
        ga = GoogleAccount() #my model
        ga.user = request.user
        ga.data = Pickle.dumps(at)
        ga.save()
        request.user.message_set.create(message="Your Google account has been "+
            "successfully added.")
        return HttpResponseRedirect('/oauth')
