import os
from functools import wraps
from flask import Flask, g, request, session
from flask import url_for, render_template, redirect, jsonify, flash
from werkzeug import secure_filename
import tweepy

app = Flask(__name__)
app.secret_key = 'aG7JBuQ2Esr1q8vyERD7HGYWuyB5ULAJavf7qSFKzpSm3NNoVfEcDwB1cmrPQYcH'
app.config['TWEEPY_CONSUMER_KEY'] = 'NwN1VkN1Vn7WQ4C0aXg'
app.config['TWEEPY_CONSUMER_SECRET'] = 'bHaaonUNb2WxtGHESOJzuaLwdHAhPoezmMNw4t2HQ'
app.config['UPLOAD_FOLDER'] = '/tmp'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = set(['jpg', 'jpeg', 'gif', 'png'])

class User(object):
	id = '0'
	name = 'Unknown'
	username = 'unknown'
	avatar_url = 'https://si0.twimg.com/sticky/default_profile_images/default_profile_2.png'
	access_token = None
	access_token_secret = None
	
	_api = None
	
	def __init__(self, obj = None, access_token = None, access_token_secret = None):
		if obj is not None:
			self.id = obj.id_str
			self.name = obj.name
			self.username = obj.screen_name
			self.avatar_url = obj.profile_image_url
		self.access_token = access_token
		self.access_token_secret = access_token_secret
	
	def get_api(self):
		if not self._api:
			auth = tweepy.OAuthHandler(
				app.config.get('TWEEPY_CONSUMER_KEY'),
				app.config.get('TWEEPY_CONSUMER_SECRET')
			)
			auth.set_access_token(self.access_token, self.access_token_secret)
			self._api = tweepy.API(auth)
		return self._api
	
	def save(self):
		for attr in [ attr for attr in vars(self) if not attr.startswith('_') ]:
			session[self.__class__.__name__.lower() + '_' + attr] = getattr(self, attr)
		return self
	
	def load(self):
		for attr in [ attr for attr in dir(self) if not attr.startswith('_') ]:
			setattr(self, attr, session.get(self.__class__.__name__.lower() + '_' + attr, getattr(self, attr)))
		return self



def login_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if g.user is None:
			return redirect(url_for('login', next=request.url))
		return f(*args, **kwargs)
	return decorated_function

@app.before_request
def check_login():
	if 'user_access_token' and 'user_access_token_secret' in session:
		g.user = User().load()
	else:
		g.user = None

@app.route('/')
def home():
	return render_template('home.html')

@app.route('/login/')
def login(next=None):
	if request.args.get('oauth_verifier', '') and 'request_token_key' in session and 'request_token_secret' in session:
		verifier = request.args.get('oauth_verifier', '')
		auth = tweepy.OAuthHandler(
			app.config.get('TWEEPY_CONSUMER_KEY'),
			app.config.get('TWEEPY_CONSUMER_SECRET')
		)
		auth.set_request_token(
			session.get('request_token_key', ''),
			session.get('request_token_secret')
		)
		del session['request_token_key']
		del session['request_token_secret']
	
		try:
			token = auth.get_access_token(verifier)
		except:
			#return "Can't get Access Token"
			return redirect(url_for('login'))
		
		api = tweepy.API(auth)
		try:
			obj = api.verify_credentials()
		except:
			return "Couldn't verify credentials"
		
		user = User(obj, token.key, token.secret)
		user.save()
		return redirect(url_for('home'))
	
	auth = tweepy.OAuthHandler(
		app.config.get('TWEEPY_CONSUMER_KEY'),
		app.config.get('TWEEPY_CONSUMER_SECRET'),
		url_for('login', _external=True)
	)
	
	try:
		redirect_url = auth.get_authorization_url()
	except:
		return "Can't get Sign-in URL"
	
	session['request_token_key'] = auth.request_token.key
	session['request_token_secret'] = auth.request_token.secret
	return redirect(redirect_url)

@app.route('/logout/')
def logout():
	session.clear()
	return redirect(url_for('home'))

@app.route('/avatar/', methods=['GET', 'POST'])
@login_required
def avatar():
	if request.method == 'POST':
		if 'file' in request.files and request.files['file'].filename.split('.')[-1] in ALLOWED_EXTENSIONS:
			f = request.files['file']
			filename = secure_filename('tweetool_avatar_tmp_%s.%s' % (g.user.id, f.filename.split('.')[-1]))
			path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
			f.save(path)
			
			if os.path.getsize(path) > 700*1024:
				flash("Image must be smaller than 700kb")
				return redirect(url_for('avatar'))
			
			api = g.user.get_api()
			try:
				api.update_profile_image(filename=path)
				success = True
			except:
				flash("Twitter refused the request")
				success = False
			finally:
				os.remove(path)
			
			return redirect(url_for('avatar_complete' if success else 'avatar'))
	
	return render_template('avatar.html')

@app.route('/avatar/complete/')
def avatar_complete():
	return render_template('avatar_complete.html')

if __name__ == '__main__':
	app.run(debug=True)
