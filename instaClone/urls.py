from django.conf.urls import url
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from myapp.views import signup_view, login_view, feed_view, post_view, like_view, comment_view, upvote_view, logout_view

urlpatterns = [
  url('logout/', logout_view),
  url('upvote/', upvote_view),
  url('post/', post_view),
  url('feeds/', feed_view),
  url('like/', like_view),
  url('comment/', comment_view),
  url('login/', login_view),
  url('', signup_view),
]