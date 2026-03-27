from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import random
import os
from functools import wraps
from dateutil import parser
from ml_model import predict_wait_time
from twilio_alerts import send_alert
from flask_socketio import SocketIO, emit


app = Flask(__name__)
socketio = SocketIO(app)


# For development: generate a new secret key on each restart to invalidate old sessions.
# For production, you must use a consistent, securely generated key.
app.secret_key = os.urandom(24)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///queue_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Token(db.Model):
    id = db.Column(db.String(20), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, default=30)
    priority = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='waiting')
    position = db.Column(db.Integer)
    estimated_wait = db.Column(db.Float)
    joined_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    called_at = db.Column(db.DateTime, nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    counter_id = db.Column(db.Integer, nullable=True)
    
    user = db.relationship('User', backref=db.backref('tokens', lazy=True))

class Counter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='open')
    current_token_id = db.Column(db.String(20), nullable=True)

# Create tables
with app.app_context():
    db.create_all()
    
    # Create default admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@queue.com',
            is_admin=True
        )
        admin.set_password('admin123')  # Change this in production!
        db.session.add(admin)
        db.session.commit()
    
    # Create counters if not exist
    if Counter.query.count() == 0:
        counters = [
            Counter(id=1, name='Counter 1', status='open'),
            Counter(id=2, name='Counter 2', status='closed'),
            Counter(id=3, name='Counter 3', status='open')
        ]
        db.session.add_all(counters)
        db.session.commit()

# Serve favicon
@app.route('/favicon.ico')
def favicon():
    return '', 204

# Queue System Class
class QueueSystem:
    
     
    def __init__(self):
        self.avg_service_time = 4.5
        # Centralized definition for rush hours (e.g., 9-11 AM, 2-4 PM)
        self.rush_hours = list(range(9, 12)) + list(range(14, 17))

    def is_rush_hour(self):
        """Checks if the current time is within the defined rush hours."""
        return datetime.datetime.now().hour in self.rush_hours
        
    def auto_allocate_counters(self):
        waiting_count = Token.query.filter_by(status='waiting').count()

        if waiting_count > 20:
            counters = Counter.query.all()
            for c in counters:
                c.status = "open"
            db.session.commit()

        elif waiting_count < 5:
            counters = Counter.query.all()
            for c in counters:
                if c.id == 1:
                    c.status = "open"
                else:
                    c.status = "closed"
            db.session.commit()

    
    def generate_token_id(self):
        last_token = Token.query.order_by(Token.id.desc()).first()
        if last_token:
            last_num = int(last_token.id[1:])
            return f"T{last_num + 1}"
        return "T1001"
    def join_queue(self, name, user_id=None, age=30, priority=False):
       token_id = self.generate_token_id()

    # Calculate position
       waiting_tokens = Token.query.filter_by(status='waiting').count()
       position = waiting_tokens + 1

    # AI Prediction
       predicted_time = predict_wait_time(
          people=position,
          avg_service=6,
          is_peak=1 if self.is_rush_hour() else 0
    )

       estimated_wait = predicted_time  # Save predicted wait time

    # Create token
       token = Token(
        id=token_id,
        user_id=user_id,
        name=name,
        age=age,
        priority=priority or age > 60,
        status='waiting',
        position=position,
        estimated_wait=estimated_wait,
        joined_at=datetime.datetime.utcnow()
    )

       db.session.add(token)
       db.session.commit()
       self.auto_allocate_counters()



       return {
        'id': token_id,
        'name': name,
        'age': age,
        'priority': priority or age > 60,
        'status': 'waiting',
        'position': position,
        'estimated_wait': estimated_wait,
        'joined_at': token.joined_at.isoformat()
    }

    
   
    def calculate_wait_time(self, position, priority=False):
        open_counters = Counter.query.filter_by(status='open').count()
        
        # If no counters are open, wait time is effectively infinite, but we can return a high number.
        if open_counters == 0:
            return 999

        # Effective service time is distributed across open counters
        effective_service_time = self.avg_service_time / open_counters
        base_wait = position * effective_service_time
        if priority:
            base_wait *= 0.5
        base_wait += random.uniform(-1, 2)
        return max(1, round(base_wait, 1))
    
    def get_queue_stats(self):
        total = Token.query.filter_by(status='waiting').count()
        priority_count = Token.query.filter_by(status='waiting', priority=True).count()
        
        waiting_tokens = Token.query.filter_by(status='waiting').all()
        if waiting_tokens:
            avg_wait = sum(t.estimated_wait for t in waiting_tokens) / len(waiting_tokens)
        else:
            avg_wait = 0
        
        open_counters = Counter.query.filter_by(status='open').count()
        
        return {
            'total_in_queue': total,
            'priority_count': priority_count,
            'average_wait_time': round(avg_wait, 1),
            'is_rush_hour': self.is_rush_hour(),
            'counters_open': open_counters
        }
    
    def process_token(self, token_id, counter_id=None):
        token = Token.query.get(token_id)
        if token and token.status in ['waiting', 'called']:
            token.status = 'processed'
            token.called_at = token.called_at or datetime.datetime.utcnow() # Set call time if not already set
            token.processed_at = datetime.datetime.utcnow()
            if counter_id:
                token.counter_id = counter_id
            
            # Update positions of tokens behind the processed one
            if token.position is not None:
                tokens_to_update = Token.query.filter(Token.status == 'waiting', Token.position > token.position).all()
                for t in tokens_to_update:
                    t.position -= 1
                    t.estimated_wait = self.calculate_wait_time(t.position, t.priority)

            db.session.commit()
            return True
        return False
    
    def skip_token(self, token_id):
        token = Token.query.get(token_id)
        if token and token.status == 'waiting':
            old_position = token.position
            new_position = Token.query.filter_by(status='waiting').count()
            
            # Update positions of tokens that were after the skipped one
            tokens_to_update = Token.query.filter(Token.status == 'waiting', Token.position > old_position).all()
            for t in tokens_to_update:
                t.position -= 1
                t.estimated_wait = self.calculate_wait_time(t.position, t.priority)
            
            token.position = new_position
            token.estimated_wait = self.calculate_wait_time(new_position, token.priority)
            db.session.commit()
            return True
        return False

    def call_next_token(self, counter_id):
        counter = Counter.query.get(counter_id)
        if not counter or counter.status != 'open':
            return None # Counter not available
        
        # Find next token to be called (highest priority, then lowest position)
        next_token = Token.query.filter_by(status='waiting').order_by(Token.priority.desc(), Token.position).first()
        
        if next_token:
            next_token.status = 'called'
            next_token.called_at = datetime.datetime.utcnow()
            next_token.counter_id = counter_id
            counter.current_token_id = next_token.id
            db.session.commit()
            return next_token
        return None

# Initialize queue system
queue_system = QueueSystem()

# Add some demo tokens
with app.app_context():
    if db.session.query(Token).count() == 0:
        demo_tokens = [
            ("John Doe", 45, False),
            ("Alice Smith", 72, True),
            ("Bob Johnson", 35, False),
            ("Carol Williams", 68, True),
            ("David Brown", 29, False),
        ]
        
        for name, age, priority in demo_tokens:
            queue_system.join_queue(name, age=age, priority=priority)

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('admin_login')) # This is correct, points to the route we are adding back
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Template filter for formatting datetime strings
@app.template_filter('format_datetime')
def format_datetime(value, format='%I:%M %p, %b %d'):
    if isinstance(value, str):
        value = parser.parse(value)
    return value.strftime(format)

# Routes
@app.route('/')
def index():
    stats = queue_system.get_queue_stats()
    return render_template('index.html', stats=stats)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validation
        if not username or not email or not password:
            return render_template('register.html', error='All fields are required')
        
        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')
        
        if User.query.filter_by(username=username).first():
            return render_template('register.html', error='Username already exists')
        
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email already registered')
        
        # Create user
        user = User(username=username, email=email)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()
        try:
            from twilio_alerts import send_alert
            if hasattr(user, "phone") and user.phone:
                send_alert(
                    user.phone,
                    f"Welcome {username}! Your account has been created successfully."
                )
        except Exception as e:
            print("SMS error:", e)
        # ---------------------------------------------

        return redirect(url_for('login'))
    
    return render_template('register.html')

        # Redirect to login page after successful registration
    

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            # Explicitly prevent admins from using the regular user login page.
            if user.is_admin:
                return render_template('login.html', error='Administrators must use the admin login page.')
            
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            session.permanent = False  # Ensure session expires when browser closes
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_admin:
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = True
            session.permanent = False  # Ensure session expires when browser closes
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid admin credentials.')
    
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    user = User.query.get(session['user_id'])
    # Explicitly redirect any admin user away from the user dashboard
    if user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Get latest token or create demo
    token_id = Token.query.filter_by(user_id=user.id).order_by(Token.joined_at.desc()).with_entities(Token.id).first()
    token = Token.query.get(token_id)
    
    if token:
        token_dict = {
            'id': token.id,
            'name': token.name,
            'age': token.age,
            'priority': token.priority,
            'status': token.status,
            'position': token.position,
            'estimated_wait': token.estimated_wait,
            'joined_at': token.joined_at.isoformat()
        }
    else:
        token_dict = {}
    
    stats = queue_system.get_queue_stats()
    return render_template('user_dashboard.html', 
                         token=token_dict, 
                         stats=stats,
                         user=user)

@app.route('/token')
@login_required
def token_page():
    user = User.query.get(session['user_id'])
    latest_token = Token.query.filter_by(user_id=user.id).order_by(Token.joined_at.desc()).first()
    
    if not latest_token:
        return redirect(url_for('index'))
    
    token_dict = {
        'id': latest_token.id,
        'name': latest_token.name,
        'age': latest_token.age,
        'priority': latest_token.priority,
        'status': latest_token.status,
        'position': latest_token.position,
        'estimated_wait': latest_token.estimated_wait,
        'joined_at': latest_token.joined_at.isoformat()
    }
    
    return render_template('token.html', token=token_dict)

@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = queue_system.get_queue_stats()
    
    active_tokens = Token.query.filter_by(status='waiting').order_by(Token.priority.desc(), Token.position).all()
    
    tokens_list = []
    for token in active_tokens:
        tokens_list.append({
            'id': token.id,
            'name': token.name,
            'age': token.age,
            'priority': token.priority,
            'position': token.position,
            'estimated_wait': token.estimated_wait,
            'joined_at': token.joined_at.isoformat()
        })
    
    counters = Counter.query.all()
    counters_list = []
    for counter in counters:
        counters_list.append({
            'id': counter.id,
            'name': counter.name,
            'status': counter.status,
            'current_token': counter.current_token_id
        })
    
    return render_template('admin_dashboard.html', 
                         stats=stats,
                         tokens=tokens_list,
                         counters=counters_list)


@app.route('/elderly-priority')
def elderly_priority():
    return render_template('elderly_priority.html')

@app.route('/join_priority_queue', methods=['POST'])
def join_priority_queue():
    """Handles form submission from the elderly/priority page."""
    try:
        name = request.form.get('name')
        age = int(request.form.get('age', 30))
        
        # Join the queue with priority set to True
        token_info = queue_system.join_queue(name=name, age=age, priority=True)

        # Store token_id in session to link it to the user if they log in later
        session['last_token_id'] = token_info['id']

        return jsonify({
            "status": "success",
            "token": token_info['id'],
            "eta": f"{token_info['estimated_wait']} minutes"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# API Routes
@app.route('/api/join-queue', methods=['POST'])
@login_required
def join_queue():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        user = User.query.get(session['user_id'])
        name = data.get('name', user.username).strip()
        age = data.get('age', 30)
        priority = data.get('priority', False)
        
        token = queue_system.join_queue(name, user.id, age, priority)
        
        return jsonify({
            'success': True, 
            'token': token,
            'redirect': url_for('user_dashboard')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/queue-stats')
def get_queue_stats():
    stats = queue_system.get_queue_stats()
    return jsonify(stats)

@app.route('/api/wait-time-predictions')
@admin_required
def wait_time_predictions():
    """Provides data for the wait time prediction chart."""
    current_queue_size = Token.query.filter_by(status='waiting').count()
    
    labels = [f"Position {current_queue_size + i}" for i in range(1, 11)]
    data = [queue_system.calculate_wait_time(current_queue_size + i) for i in range(1, 11)]
    
    return jsonify({
        'labels': labels,
        'data': data
    })

@app.route('/api/user-token/<token_id>')
@login_required
def get_user_token(token_id):
    token = Token.query.get(token_id)
    if token and token.user_id == session['user_id']:
        token_dict = {
            'id': token.id,
            'name': token.name,
            'age': token.age,
            'priority': token.priority,
            'status': token.status,
            'position': token.position,
            'estimated_wait': token.estimated_wait,
            'joined_at': token.joined_at.isoformat()
        }
        return jsonify(token_dict)
    return jsonify({'error': 'Token not found'}), 404

@app.route('/api/process-token/<token_id>', methods=['POST'])
@admin_required
def process_token(token_id):
    token = Token.query.get(token_id)
    if not token:
        return jsonify({'success': False, 'error': 'Token not found'}), 404

    counter_id = token.counter_id
    success = queue_system.process_token(token_id, counter_id)

    if success and counter_id:
        # Free up the counter and call the next person
        counter = Counter.query.get(counter_id)
        if counter:
            counter.current_token_id = None
            db.session.commit()
            # Automatically call the next token to this now-free counter
            queue_system.call_next_token(counter_id)

    if success:
        return jsonify({'success': True, 'redirect_url': url_for('admin_dashboard')})
    return jsonify({'success': False, 'error': 'Failed to process token'})

@app.route('/api/skip-token/<token_id>', methods=['POST'])
@admin_required
def skip_token(token_id):
    success = queue_system.skip_token(token_id)
    return jsonify({'success': success})

@app.route('/api/call-token/<token_id>', methods=['POST'])
@admin_required
def call_token(token_id):
    # Find an open counter
    open_counter = Counter.query.filter_by(status='open', current_token_id=None).first()

    if not open_counter:
        return jsonify({'success': False, 'error': 'No open counters available to assign the token.'}), 400

    token = Token.query.get(token_id)
    if not token or token.status != 'waiting':
        return jsonify({'success': False, 'error': 'Token is not available to be called.'}), 404

    # Assign token to the counter
    token.counter_id = open_counter.id
    token.called_at = datetime.datetime.utcnow()
    open_counter.current_token_id = token.id
    db.session.commit()

    return jsonify({'success': True, 'message': f'Token {token_id} called to {open_counter.name}.'})

@app.route('/api/update-counter/<int:counter_id>', methods=['POST'])
@admin_required
def update_counter(counter_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        status = data.get('status')
        if status not in ['open', 'closed']:
            return jsonify({'success': False, 'error': 'Invalid status'}), 400
        
        counter = Counter.query.get(counter_id)
        if counter:
            counter.status = status
            db.session.commit()
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'error': 'Counter not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    # -------------------------------
# AUTO COUNTER ALLOCATION + AI WAIT-TIME API

@app.route("/api/wait-time")
def api_wait():
    """
    AI-based wait time API
    Example call: /api/wait-time?people=10
    """
    people = request.args.get("people", type=int, default=1)
    predicted = predict_wait_time(people, 6, 0)
    return {"predicted_time": predicted}

@app.route('/db-view')
@admin_required
def db_view():
    """View database content (for development only)"""
    users = User.query.all()
    tokens = Token.query.all()
    counters = Counter.query.all()
    
    return render_template('db_view.html', 
                         users=users, 
                         tokens=tokens, 
                         counters=counters)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.datetime.now().isoformat()})

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, host='127.0.0.1')
