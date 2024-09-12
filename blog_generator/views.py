from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
from pytube import YouTube
import yt_dlp
import os
import assemblyai as aai
from .models import BlogPost
# from openai import OpenAI
# import openai
from g4f.client import Client
client = Client()

# client = OpenAI(api_key=os.getenv('open_api_key'))


from .models import BlogPost
import logging


logging.basicConfig(level=logging.DEBUG)
# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)


        # get yt title
        title = yt_title(yt_link)

        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error': " Failed to get transcript"}, status=500)


        # use chatgpt to generate the blog
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({'error': " Failed to generate blog article"}, status=500)

        # save blog article to database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()

        # return blog article as a response
        return JsonResponse({'content': blog_content})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def yt_title(link):
    yt = YouTube(link)
    title = yt.title
    return title

def download_audio(link):
    try:
        logging.debug(f"Downloading audio from link: {link}")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(settings.MEDIA_ROOT, '%(title)s.%(ext)s'),  # Save to MEDIA_ROOT
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(link, download=True)

        # The downloaded file path
        out_file = os.path.join(settings.MEDIA_ROOT, f"{result['title']}.mp3")

        # Ensure the file exists and is not empty
        if not os.path.exists(out_file) or os.path.getsize(out_file) == 0:
            raise Exception("Failed to download or convert audio file")

        logging.debug(f"Audio file successfully downloaded and converted: {out_file}")
        return out_file

    except Exception as e:
        logging.error(f"An error occurred during audio download: {e}")
        return None

def get_transcription(link):
    try:
        logging.debug("Downloading audio...")
        audio_file = download_audio(link)
        logging.debug(f"Audio file downloaded: {audio_file}")

        ASSEMBLY_AI_KEY = os.getenv('ASSEMBLYAI_API_KEY')
        if not ASSEMBLY_AI_KEY:
            raise ValueError("API key for AssemblyAI is not set")

        logging.debug("Setting API key...")
        aai.settings.api_key = ASSEMBLY_AI_KEY

        logging.debug("Initializing transcriber...")
        transcriber = aai.Transcriber()
        logging.debug("Transcribing audio...")
        transcript = transcriber.transcribe(audio_file)

        logging.debug("Transcription successful")
        return transcript.text
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None

# OPEN_AI_KEY = os.getenv('open_api_key')
def generate_blog_from_transcription(transcription):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write a comprehensive blog article based on the following transcript. "
                    f"Make it look like a proper blog article, not a YouTube video script:\n\n{transcription}\n\nArticle:"
                )
            }
        ],
    )

    return response.choices[0].message.content



def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})

    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message':error_message})
        else:
            error_message = 'Password do not match'
            return render(request, 'signup.html', {'error_message':error_message})

    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')