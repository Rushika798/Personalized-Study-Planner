from flask import Flask, render_template, request, session, redirect, url_for, flash
from datetime import datetime, timedelta, time
import csv # Import the csv module
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key' # Replace with a strong, unique secret key

# Define file paths for persistence
USERS_FILE = 'users.csv'
PLANS_FILE = 'plans.csv' # Changed to .csv

# Global dictionaries to hold loaded data
users = {}
# plans will store data as: {'username': {'YYYY-MM-DD': [{'task_dict'}, ...]}, ...}
plans = {}

# --- Helper functions for loading and saving data (CSV specific) ---

def load_users_from_csv():
    """Loads user data from users.csv."""
    loaded_users = {}
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, mode='r', newline='') as file:
            reader = csv.reader(file)
            # Skip header if it exists
            try:
                first_row = next(reader)
                if first_row != ['username', 'password']: # Check if it's a header
                    loaded_users[first_row[0]] = first_row[1] # If not header, process first row
            except StopIteration:
                pass # File is empty

            for row in reader:
                if len(row) == 2:
                    loaded_users[row[0]] = row[1]
    return loaded_users

def save_users_to_csv(users_data):
    """Saves user data to users.csv."""
    with open(USERS_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['username', 'password']) # Write header
        for username, password in users_data.items():
            writer.writerow([username, password])

def load_plans_from_csv():
    """Loads study plan data from plans.csv."""
    loaded_plans = {}
    if os.path.exists(PLANS_FILE):
        with open(PLANS_FILE, mode='r', newline='') as file:
            reader = csv.DictReader(file) # Use DictReader for easier column access
            for row in reader:
                username = row.get('username')
                date_str = row.get('date')
                if username and date_str:
                    if username not in loaded_plans:
                        loaded_plans[username] = {}
                    if date_str not in loaded_plans[username]:
                        loaded_plans[username][date_str] = []
                    
                    # Reconstruct the task dictionary, ensuring types are correct if needed later
                    task = {
                        'subject': row.get('subject'),
                        'topic': row.get('topic'),
                        'hours': float(row.get('hours', 0.0)), # Convert hours back to float
                        'start_time': row.get('start_time'),
                        'end_time': row.get('end_time'),
                        'status': row.get('status')
                    }
                    loaded_plans[username][date_str].append(task)
    return loaded_plans

def save_plans_to_csv(plans_data):  
    """Saves study plan data to plans.csv."""
    # Define the fieldnames (columns) for the CSV
    fieldnames = ['username', 'date', 'subject', 'topic', 'hours', 'start_time', 'end_time', 'status']
    
    with open(PLANS_FILE, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader() # Write the header row
        
        for username, user_plan_by_date in plans_data.items():
            for date_str, tasks_list in user_plan_by_date.items():
                for task in tasks_list:
                    # Create a flat row dictionary for CSV
                    row = {
                        'username': username,
                        'date': date_str,
                        'subject': task.get('subject'),
                        'topic': task.get('topic'),
                        'hours': task.get('hours'),
                        'start_time': task.get('start_time'),
                        'end_time': task.get('end_time'),
                        'status': task.get('status')
                    }
                    writer.writerow(row)

# --- Load data when the application starts ---
@app.before_first_request
def load_all_data():
    global users, plans
    users = load_users_from_csv()
    plans = load_plans_from_csv()
    print(f"Loaded users: {len(users)} entries")
    print(f"Loaded plans: {len(plans)} user plans") # Count distinct users with plans


# --- Your existing calculate_plan function (no changes needed here) ---
# This function calculates the plan and returns it in the dictionary format
# which is then handled by the save_plans_to_csv function.
def calculate_plan(subjects, topics, difficulties, exam_dates, daily_study_hours, study_start_time_str):
    """
    Calculates a study plan based on subjects, difficulties, exam dates,
    daily study hours, and a preferred daily study start time.
    """
    exam_dates_dt = [datetime.strptime(ed, "%Y-%m-%d") for ed in exam_dates]
    today = datetime.now().date()
    total_difficulty = sum(difficulties)
    plan = {}

    try:
        study_start_time = datetime.strptime(study_start_time_str, '%H:%M').time()
    except ValueError:
        flash("Invalid study start time format. Please use HH:MM.", "error")
        return {}

    if not exam_dates_dt:
        return {}
    latest_exam_date = max(exam_dates_dt)
    
    daily_current_study_time = {}
    current_day = today
    while current_day <= latest_exam_date.date():
        day_str = current_day.strftime('%Y-%m-%d')
        daily_current_study_time[day_str] = study_start_time
        plan[day_str] = []
        current_day += timedelta(days=1)

    for i, subj in enumerate(subjects):
        diff = difficulties[i]
        exam_date = exam_dates_dt[i]
        topic = topics[i]

        days_available_for_subject = (exam_date.date() - today).days + 1
        if days_available_for_subject <= 0:
            flash(f"Exam date for {subj} is in the past! Please enter a future date.", "error")
            continue

        total_subject_hours = (diff / total_difficulty) * daily_study_hours * days_available_for_subject
        hours_per_day_for_subject = total_subject_hours / days_available_for_subject
        minutes_per_day_for_subject = int(hours_per_day_for_subject * 60)

        for day_offset in range(days_available_for_subject):
            study_day = today + timedelta(days=day_offset)
            day_str = study_day.strftime('%Y-%m-%d')

            if day_str not in daily_current_study_time:
                daily_current_study_time[day_str] = study_start_time
                plan[day_str] = []

            current_task_start_dt = datetime.combine(study_day, daily_current_study_time[day_str])
            current_task_end_dt = current_task_start_dt + timedelta(minutes=minutes_per_day_for_subject)

            if current_task_end_dt.date() > study_day:
                current_task_end_dt = datetime.combine(study_day, time(23, 59))

            plan[day_str].append({
                'subject': subj,
                'topic': topic,
                'hours': round(hours_per_day_for_subject, 2),
                'start_time': current_task_start_dt.strftime('%H:%M'),
                'end_time': current_task_end_dt.strftime('%H:%M'),
                'status': 'Pending'
            })
            daily_current_study_time[day_str] = current_task_end_dt.time()
            
    for day_str in plan:
        plan[day_str].sort(key=lambda x: datetime.strptime(x['start_time'], '%H:%M').time())

    plan = {date: tasks for date, tasks in plan.items() if tasks}

    return dict(sorted(plan.items()))


## --- Flask Routes (modifications needed) ---

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    global users
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users:
            flash("Username already exists. Please choose a different one.", "error")
            return render_template('register.html')
        users[username] = password
        save_users_to_csv(users) # Save users to CSV
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    global plans
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username] == password:
            session['user'] = username
            # Store the user's plan in session. It's stored as a dictionary, not JSON string here.
            # Convert to JSON string when needed by templates if they expect it, or handle in JS.
            session['study_plan_data'] = plans.get(username, {}) 
            flash(f"Welcome, {username}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password. Please try again.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been successfully logged out.", "success")
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash("Please log in to access your dashboard.", "error")
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['user'])

@app.route('/plan', methods=['GET', 'POST'])
def plan():
    global plans
    if 'user' not in session:
        flash("Please log in to create a study plan.", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = session['user']
        subjects = request.form.getlist('subject[]')
        topics = request.form.getlist('topic[]')
        difficulties_str = request.form.getlist('difficulty[]')
        exam_dates = request.form.getlist('exam_date[]')
        daily_study_hours = request.form.get('daily_hours')
        study_start_time_str = request.form.get('study_start_time')

        if not subjects or not topics or not difficulties_str or not exam_dates or \
           not daily_study_hours or not study_start_time_str:
            flash("Please ensure all fields are filled for each subject and general settings.", "error")
            return redirect(url_for('plan'))

        try:
            difficulties = [int(d) for d in difficulties_str]
            daily_study_hours = float(daily_study_hours)
            if any(d <= 0 for d in difficulties) or daily_study_hours <= 0:
                flash("Difficulty and daily study hours must be positive numbers.", "error")
                return redirect(url_for('plan'))
        except ValueError:
            flash("Invalid input for difficulty or daily hours. Please enter numbers.", "error")
            return redirect(url_for('plan'))
        
        if not (len(subjects) == len(topics) == len(difficulties) == len(exam_dates)):
            flash("Mismatch in the number of subjects, topics, difficulties, or exam dates. Please ensure all fields are correctly added for each entry.", "error")
            return redirect(url_for('plan'))

        study_plan = calculate_plan(subjects, topics, difficulties, exam_dates, daily_study_hours, study_start_time_str)
        
        if not study_plan:
            flash("Could not generate a study plan. Please check your exam dates and study start time.", "error")
            return redirect(url_for('plan'))

        plans[username] = study_plan
        save_plans_to_csv(plans) # Save plans to CSV

        session['study_plan_data'] = study_plan # Store the actual dictionary in session
        
        return render_template('plan_result.html', study_plan=study_plan, username=session['user'])

    return render_template('plan_form.html', username=session['user'])

@app.route('/today_tasks')
def today_tasks():
    if 'user' not in session:
        flash("Please log in to view your tasks.", "error")
        return redirect(url_for('login'))

    # Retrieve the plan directly from session (it's a dict, not JSON string)
    study_plan = session.get('study_plan_data') 
    if not study_plan:
        flash("No study plan found. Please create a plan first.", "info")
        return redirect(url_for('plan'))

    today_str = datetime.now().strftime('%Y-%m-%d')
    tasks = study_plan.get(today_str, [])
    
    for i, task in enumerate(tasks):
        task['date'] = today_str
        task['index'] = i

    return render_template('tasks.html', tasks=tasks, title="Today's Tasks", username=session['user'])

@app.route('/weekly_tasks')
def weekly_tasks():
    if 'user' not in session:
        flash("Please log in to view your tasks.", "error")
        return redirect(url_for('login'))

    # Retrieve the plan directly from session (it's a dict, not JSON string)
    study_plan = session.get('study_plan_data')
    if not study_plan:
        flash("No study plan found. Please create a plan first.", "info")
        return redirect(url_for('plan'))

    today = datetime.now().date()
    tasks = []

    for day_offset in range(7):
        day = today + timedelta(days=day_offset)
        day_str = day.strftime('%Y-%m-%d')
        day_tasks = study_plan.get(day_str, [])
        for i, task in enumerate(day_tasks):
            task['date'] = day_str
            task['index'] = i
            tasks.append(task)

    return render_template('tasks.html', tasks=tasks, title="Weekly Tasks", username=session['user'])

@app.route('/update_task', methods=['POST'])
def update_task():
    global plans
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']
    date = request.form['date']
    index = int(request.form['index'])
    new_status = request.form['status']

    user_plan = plans.get(username, {})
    if date in user_plan and 0 <= index < len(user_plan[date]):
        user_plan[date][index]['status'] = new_status
        plans[username] = user_plan
        save_plans_to_csv(plans) # Save changes to CSV
        session['study_plan_data'] = user_plan # Update session
        flash("Task status updated successfully!", "success")
    else:
        flash("Failed to update task. Task not found.", "error")

    return redirect(request.referrer or url_for('dashboard'))

@app.route('/delete_task', methods=['POST'])
def delete_task():
    global plans
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']
    date = request.form['date']
    index = int(request.form['index'])

    user_plan = plans.get(username, {})
    if date in user_plan and 0 <= index < len(user_plan[date]):
        del user_plan[date][index]
        if not user_plan[date]:
            del user_plan[date]
        plans[username] = user_plan
        save_plans_to_csv(plans) # Save changes to CSV
        session['study_plan_data'] = user_plan # Update session
        flash("Task deleted successfully!", "success")
    else:
        flash("Failed to delete task. Task not found.", "error")

    return redirect(request.referrer or url_for('dashboard'))

@app.route('/add_task', methods=['POST'])
def add_task():
    global plans
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']
    date = request.form['date']
    subject = request.form['subject']
    topic = request.form.get('topic', 'General')
    hours = request.form['hours']
    start_time = request.form['start_time']
    end_time = request.form['end_time']

    try:
        hours = float(hours)
        datetime.strptime(start_time, '%H:%M')
        datetime.strptime(end_time, '%H:%M')
    except ValueError:
        flash("Invalid hours or time format. Please use HH:MM for time.", "error")
        return redirect(request.referrer or url_for('dashboard'))

    task = {
        'subject': subject,
        'topic': topic,
        'hours': hours,
        'start_time': start_time,
        'end_time': end_time,
        'status': 'Pending'
    }

    user_plan = plans.get(username, {})
    if date not in user_plan:
        user_plan[date] = []
    
    user_plan[date].append(task)
    user_plan[date].sort(key=lambda x: datetime.strptime(x['start_time'], '%H:%M').time())
    
    plans[username] = user_plan
    save_plans_to_csv(plans) # Save changes to CSV
    session['study_plan_data'] = user_plan # Update session
    flash("Task added successfully!", "success")

    return redirect(request.referrer or url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)