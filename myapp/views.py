# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render, redirect
import datetime
from forms import SignUpForm, LoginForm, PostForm, LikeForm, CommentForm, UpvoteForm, SearchForm
from models import UserModel, SessionToken, PostModel, LikeModel, CommentModel
from django.contrib.auth.hashers import make_password, check_password
from datetime import timedelta
from django.utils import timezone
from imgurpython import ImgurClient
from instaClone.settings import BASE_DIR
from imgurpython import ImgurClient
from clarifai.rest import ClarifaiApp , Image as ClImage
import requests
import sendgrid

CLIENT_ID = 'f9544e46df27231'

CLIENT_SECRET = '442e3914273ccc69971a19eb17ab7bd751d55860'

PARALLEL_DOTS_KEY = "iZnVrpzvORopBRhgeycnlcCLRcyplf2xZzP2E4QPuXo"

SEND_GRID_KEY = "SG.-wxTqIzQSIS9Kryob6T7pA.RP7mpLSF3BWlQexfv52dLpm6s1g1jxcblZmTlzTb2G"

sndgrd_client = sendgrid.SendGridAPIClient(apikey=SEND_GRID_KEY)


# Create your views here.


def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            # saving data to DB
            user = UserModel(name=name, password=make_password(password), email=email, username=username)
            user.save()
            return render(request, 'success.html')
            # return redirect('login/')
    else:
        form = SignUpForm()

    return render(request, 'index.html', {'form': form})


def login_view(request):
    response_data = {}
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = UserModel.objects.filter(username=username).first()

            if user:
                if check_password(password, user.password):
                    token = SessionToken(user=user)
                    token.create_token()
                    token.save()
                    response = redirect('feeds/')
                    response.set_cookie(key='session_token', value=token.session_token)
                    return response
                else:
                    response_data['message'] = 'Incorrect Password! Please try again!'

    elif request.method == 'GET':
        form = LoginForm()

    response_data['form'] = form
    return render(request, 'login.html', response_data)


def post_view(request):
    user = check_validation(request)

    if user:
        if request.method == 'POST':
            form = PostForm(request.POST, request.FILES)
            if form.is_valid():
                image = form.cleaned_data.get('image')
                caption = form.cleaned_data.get('caption')
                post = PostModel(user=user, image=image, caption=caption)
                post.save()

                path = str(BASE_DIR + '/' +  post.image.url)
                if checkComment(caption) == 1 and checkImage(path) == 1:

                    print post.image_url
                    # adding imgur client to maintain url of images
                    # try catch edge case if connection fails or image can't be uploaded
                    try:
                        client = ImgurClient(CLIENT_ID, CLIENT_SECRET)
                        post.image_url = client.upload_from_path(path, anon=True)['link']
                    except:
                        return render(request, 'post.html', {'msg': 'Failed to upload! Try again later'})

                    post.save()
                    return render(request,'login_success.html',{'msg': 'Post added successfully!'})
                else:
                    return render(request, 'login_success.html', {'msg': 'Please avoid use of obscene language and images'})
                    post.delete()

                return redirect('/feeds/')

        else:
            form = PostForm()
        return render(request, 'post.html', {'form': form})
    else:
        return redirect('/login/')


def feed_view(request):
    response_data = {}

    user = check_validation(request)
    if user:

        posts = PostModel.objects.all().order_by('-created_on')

        for post in posts:
            existing_like = LikeModel.objects.filter(post_id=post.id, user=user).first()
            if existing_like:
                post.has_liked = True

        return render(request, 'feeds.html', {'posts': posts, 'msg':'Welcome '+user.username, 'comment_len':len(posts)})
    else:
        return redirect('/login/')


def like_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        form = LikeForm(request.POST)
        if form.is_valid():
            post_id = form.cleaned_data.get('post').id
            existing_like = LikeModel.objects.filter(post_id=post_id, user=user).first()
            if not existing_like:
                LikeModel.objects.create(post_id=post_id, user=user)
            else:
                existing_like.delete()
            return redirect('/feeds/')
    else:
        return redirect('/login/')


def comment_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            post_id = form.cleaned_data.get('post').id
            comment_text = form.cleaned_data.get('comment_text')
            comment = CommentModel.objects.create(user=user, post_id=post_id, comment_text=comment_text)
            comment.save()
            return redirect('/feeds/')
        else:
            return redirect('/feeds/')
    else:
        return redirect('/login')


def logout_view(request):

    user = check_validation(request)

    if user is not None:
        latest_sessn = SessionToken.objects.filter(user=user).last()
        if latest_sessn:
            latest_sessn.delete()
            return redirect("/login/")
            # how to get cookies in python to delete cookie n session


def comment_email(commentor, to_email):
    msg_payload = {
        "personalizations": [
            {
                "to": [
                    {
                        "email": to_email
                    }
                ],
                "subject": 'Your post is been noticed!'
            }
        ],
        "from": {
            "email": "admin@sociokids.com",
            "name": 'SocioAdmin'
        },
        "content": [
            {
                "type": "text/html",
                "value": '<h1>SocioKids</h1><br><br> ' + commentor + ' just commented on your post. <br> <br><h2><a href="sociokids.com">Have a look </a></h2>'

            }
        ]
    }
    response = sndgrd_client.client.mail.send.post(request_body=msg_payload)
    print response


def checkImage(path):
    app = ClarifaiApp(api_key='db9fc8c5cc4445179b039488b922c7ab')

    # get the general model
    try:
        model = app.models.get('general-v1.3')
        image = ClImage(file_obj=open(path, 'rb'))
        pred = model.predict([image])

        for i in range(0, len(pred['outputs'][0]['data']['concepts'])):
             if pred['outputs'][0]['data']['concepts'][i]['name'] == "adult":
                 if pred['outputs'][0]['data']['concepts'][i]['value'] > 0.5:
                     return 0
                 else:
                     return 1
             else:
                 return 1
        return 0
    except:
        return 0


def checkComment(commenttext):
    req_json = None
    req_url = "https://apis.paralleldots.com/abuse"
    payload = {
  "text": commenttext,
  "apikey": PARALLEL_DOTS_KEY
}
    # 1 is for non abusive and 0 is for abusive
    try:
        req_json = requests.post(req_url, payload).json()
        if req_json is not None:
            # sentiment = req_json['sentiment']
            print req_json['sentence_type']
            print req_json['confidence_score']
            if req_json['sentence_type'] == "Non Abusive":
                if req_json['confidence_score'] > 0.60:
                    return 1
                else:
                    return 0
            else:
                return 0
    except:
        return 0


@property
def comments(self):
    return CommentModel.objects.filter(post=self).order_by('created_on')


def upvote_view(request):
    user = check_validation(request)
    comment = None
    print "upvote view"
    if user and request.method == 'POST':

        form = UpvoteForm(request.POST)
        if form.is_valid():
            print form.cleaned_data

            comment_id = int(form.cleaned_data.get('id'))

            comment = CommentModel.objects.filter(id=comment_id).first()
            print "upvoted not yet"

            if comment is not None:
                # print ' unliking post'
                print "upvoted"
                comment.upvote_num += 1
                comment.save()
                print comment.upvote_num
            else:
                print 'stupid mistake'
                #liked_msg = 'Unliked!'
        else:
            print "not valid"
            return redirect('/feeds/')
    else:
        return redirect('/login/')


# For validating the session
def check_validation(request):
    if request.COOKIES.get('session_token'):
        session = SessionToken.objects.filter(session_token=request.COOKIES.get('session_token')).first()
        if session:
            time_to_live = session.created_on + timedelta(days=1)
            if time_to_live > timezone.now():
                return session.user
    else:
        return None


def query_based_search_view(request):

    user = check_validation(request)
    if user:
        if request.method == "GET":
            searchForm = SearchForm(request.GET)
            if searchForm.is_valid():
                print 'valid'
                username_query = searchForm.cleaned_data.get('searchquery')
                print username_query
                user_with_query = UserModel.objects.filter(username=username_query).first();
                posts = PostModel.objects.filter(user=user_with_query)
                return render(request, 'feeds.html',{'posts':posts})
            else:
                return redirect('/feeds/')
    else:
        return redirect('/login/')