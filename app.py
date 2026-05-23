from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify, render_template_string, get_flashed_messages, Response
import os, zipfile, subprocess, signal, shutil, json, sys, uuid, datetime, threading, time, re
from functools import wraps

app = Flask(__name__)
app.secret_key = "BLACK_ADMIN_3D_HOSTING_2026"

# --- Master Admin Credentials ---
ADMIN_USERNAME = "BLACK"
ADMIN_PASSWORD = "BLACK_777"

UPLOAD_FOLDER = "uploads"
USER_DATA_FILE = "users.json"
PLANS_FILE = "plans.json"
SUBSCRIPTIONS_FILE = "subscriptions.json"
PAYMENTS_FILE = "payments.json"
MAX_RUNNING = 1 

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
processes = {}
process_output = {}

# ---------- Data Management ----------
def load_json(filename, default=None):
    if default is None:
        default = {}
    if os.path.exists(filename):
        with open(filename, "r") as f:
            try:
                return json.load(f)
            except:
                return default
    return default

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def load_users():
    return load_json(USER_DATA_FILE)

def save_users(users):
    save_json(USER_DATA_FILE, users)

def load_plans():
    return load_json(PLANS_FILE, {
        "starter": {
            "id": "starter",
            "name": "Starter",
            "price": 0,
            "ram": "512 MB",
            "storage": "1 GB",
            "bots": 1,
            "features": ["Community Support", "Basic Analytics"],
            "popular": False,
            "active": True
        },
        "pro": {
            "id": "pro",
            "name": "Pro",
            "price": 5,
            "ram": "2 GB",
            "storage": "10 GB",
            "bots": 5,
            "features": ["Priority Support", "Custom Domain", "Daily Backups"],
            "popular": True,
            "active": True
        },
        "enterprise": {
            "id": "enterprise",
            "name": "Enterprise",
            "price": 15,
            "ram": "8 GB",
            "storage": "50 GB",
            "bots": 999,
            "features": ["24/7 Dedicated Support", "Custom Domain + SSL", "Real-time Monitoring"],
            "popular": False,
            "active": True
        }
    })

def save_plans(plans):
    save_json(PLANS_FILE, plans)

def load_subscriptions():
    return load_json(SUBSCRIPTIONS_FILE)

def save_subscriptions(subs):
    save_json(SUBSCRIPTIONS_FILE, subs)

def load_payments():
    return load_json(PAYMENTS_FILE)

def save_payments(payments):
    save_json(PAYMENTS_FILE, payments)

def get_user_subscription(username):
    subs = load_subscriptions()
    return subs.get(username, {
        "plan": "starter",
        "expires": None,
        "active": True,
        "purchased_at": None
    })

def get_user_limits(username):
    plan_id = get_user_subscription(username)["plan"]
    plans = load_plans()
    plan = plans.get(plan_id, plans["starter"])
    return {
        "ram": plan["ram"],
        "storage": plan["storage"],
        "max_bots": plan["bots"]
    }

# ---------- Security ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Bot Logic ----------
def start_app(user, app_name):
    user_dir = os.path.join(UPLOAD_FOLDER, user)
    app_dir = os.path.join(user_dir, app_name)
    zip_path = os.path.join(app_dir, "app.zip")
    extract_dir = os.path.join(app_dir, "extracted")
    log_path = os.path.join(app_dir, "logs.txt")

    if not os.path.exists(zip_path):
        return False, "ZIP file not found"
    
    limits = get_user_limits(user)
    
    if (user, app_name) in processes:
        return False, "Already running"

    # Extract if not exists
    if not os.path.exists(extract_dir):
        shutil.rmtree(extract_dir, ignore_errors=True)
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(extract_dir)

    # Find main file
    found_main, target_dir = None, extract_dir
    for root, dirs, files in os.walk(extract_dir):
        if "requirements.txt" in files and not os.path.exists(os.path.join(root, "requirements_installed.txt")):
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", os.path.join(root, "requirements.txt")])
                with open(os.path.join(root, "requirements_installed.txt"), "w") as f:
                    f.write("installed")
            except Exception as e:
                print(f"pip install error: {e}")
        
        for f in files:
            if f in ["main.py", "app.py", "bot.py"]:
                found_main = os.path.join(root, f)
                target_dir = root
                break
        if found_main:
            break

    if not found_main:
        return False, "No main.py/app.py/bot.py found"

    # Start process
    try:
        log = open(log_path, "a")
        p = subprocess.Popen(
            [sys.executable, os.path.basename(found_main)], 
            cwd=target_dir, 
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        processes[(user, app_name)] = p
        
        process_output[(user, app_name)] = []
        
        def read_output():
            try:
                for line in iter(p.stdout.readline, ''):
                    if line:
                        process_output[(user, app_name)].append(line)
                        if len(process_output[(user, app_name)]) > 500:
                            process_output[(user, app_name)].pop(0)
                        log.write(line)
                        log.flush()
            except:
                pass
            finally:
                log.close()
        
        threading.Thread(target=read_output, daemon=True).start()
        
        return True, "Started successfully"
    except Exception as e:
        return False, str(e)

def stop_app(user, app_name):
    key = (user, app_name)
    p = processes.get(key)
    if p:
        try:
            p.terminate()
            try:
                p.wait(timeout=5)
            except:
                p.kill()
                p.wait()
        except Exception as e:
            print(f"Error stopping: {e}")
        finally:
            processes.pop(key, None)
            return True
    return False

def restart_app(user, app_name):
    stop_app(user, app_name)
    time.sleep(1)
    return start_app(user, app_name)

# ---------- Routes ----------
@app.route("/")
def landing():
    plans = load_plans()
    return render_template_string(LANDING_TEMPLATE, plans=plans)

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'username' in session and not session.get('is_admin'):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("access_key", "").strip()
        users = load_users()
        
        if u in users and users[u] == p:
            session['username'] = u
            session['is_admin'] = False
            return redirect(url_for("dashboard"))
        elif u not in users:
            users[u] = p
            save_users(users)
            
            subs = load_subscriptions()
            subs[u] = {
                "plan": "starter",
                "expires": None,
                "active": True,
                "purchased_at": datetime.datetime.now().isoformat()
            }
            save_subscriptions(subs)
            
            session['username'] = u
            session['is_admin'] = False
            return redirect(url_for("dashboard"))
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Invalid credentials")
    
    return render_template_string(LOGIN_TEMPLATE, error=None)

@app.route("/dashboard")
@login_required
def dashboard():
    user = session['username']
    user_dir = os.path.join(UPLOAD_FOLDER, user)
    os.makedirs(user_dir, exist_ok=True)
    
    sub = get_user_subscription(user)
    plans = load_plans()
    current_plan = plans.get(sub["plan"], plans["starter"])
    limits = get_user_limits(user)
    
    apps = []
    app_count = 0
    if os.path.exists(user_dir):
        for name in os.listdir(user_dir):
            app_path = os.path.join(user_dir, name)
            if os.path.isdir(app_path):
                app_count += 1
                log_file = os.path.join(app_path, "logs.txt")
                log_data = ""
                if os.path.exists(log_file):
                    try:
                        with open(log_file, "r") as f:
                            log_data = f.read()[-1000:]
                    except:
                        log_data = "Error reading logs"
                
                key = (user, name)
                if key in process_output:
                    live_output = ''.join(process_output[key][-50:])
                    if live_output:
                        log_data = live_output
                
                apps.append({
                    "name": name,
                    "running": key in processes,
                    "log": log_data
                })
    
    messages = get_flashed_messages(with_categories=True)
    
    return render_template_string(DASHBOARD_TEMPLATE, 
                         apps=apps, 
                         current_plan=current_plan,
                         limits=limits,
                         app_count=app_count,
                         sub=sub,
                         session=session,
                         messages=messages)

@app.route("/upload", methods=["POST"])
@login_required
def upload_app():
    user = session['username']
    limits = get_user_limits(user)
    user_dir = os.path.join(UPLOAD_FOLDER, user)
    
    current_apps = len([d for d in os.listdir(user_dir) if os.path.isdir(os.path.join(user_dir, d))]) if os.path.exists(user_dir) else 0
    
    if current_apps >= limits["max_bots"]:
        flash(f"Upgrade required! You can only host {limits['max_bots']} bot(s) on your current plan.", "error")
        return redirect(url_for("dashboard"))
    
    file = request.files.get("file")
    if file and file.filename.endswith(".zip"):
        app_name = file.filename.replace(".zip", "").replace(" ", "_")
        app_dir = os.path.join(user_dir, app_name)
        
        stop_app(user, app_name)
        
        shutil.rmtree(app_dir, ignore_errors=True)
        os.makedirs(app_dir, exist_ok=True)
        file.save(os.path.join(app_dir, "app.zip"))
        flash("Bot uploaded successfully!", "success")
    
    return redirect(url_for("dashboard"))

@app.route("/run/<name>")
@login_required
def run_user(name):
    user = session['username']
    
    if (user, name) in processes:
        flash("Bot is already running!", "error")
        return redirect(url_for("dashboard"))
    
    user_running = [k for k in processes.keys() if k[0] == user]
    if len(user_running) >= MAX_RUNNING:
        stop_app(user_running[0][0], user_running[0][1])
    
    success, msg = start_app(user, name)
    if success:
        flash(f"Bot started: {msg}", "success")
    else:
        flash(f"Failed to start: {msg}", "error")
    
    return redirect(url_for("dashboard"))

@app.route("/stop/<name>")
@login_required
def stop_user(name):
    user = session['username']
    if stop_app(user, name):
        flash("Bot stopped successfully!", "success")
    else:
        flash("Bot was not running", "error")
    return redirect(url_for("dashboard"))

@app.route("/restart/<name>")
@login_required
def restart_user(name):
    user = session['username']
    success, msg = restart_app(user, name)
    if success:
        flash(f"Bot restarted: {msg}", "success")
    else:
        flash(f"Failed to restart: {msg}", "error")
    return redirect(url_for("dashboard"))

@app.route("/delete/<name>")
@login_required
def delete_user(name):
    user = session['username']
    stop_app(user, name)
    app_dir = os.path.join(UPLOAD_FOLDER, user, name)
    if os.path.exists(app_dir):
        shutil.rmtree(app_dir, ignore_errors=True)
        flash("Bot deleted successfully!", "success")
    return redirect(url_for("dashboard"))

@app.route("/console/<name>")
@login_required
def console(name):
    user = session['username']
    key = (user, name)
    
    output = ""
    if key in process_output:
        output = ''.join(process_output[key])
    
    return render_template_string(CONSOLE_TEMPLATE, 
                                bot_name=name, 
                                output=output,
                                running=key in processes)

@app.route("/console/<name>/stream")
@login_required
def console_stream(name):
    user = session['username']
    key = (user, name)
    
    def generate():
        last_len = 0
        while True:
            if key in process_output:
                current_output = process_output[key]
                if len(current_output) > last_len:
                    new_lines = current_output[last_len:]
                    yield f"data: {json.dumps({'lines': new_lines})}\n\n"
                    last_len = len(current_output)
            time.sleep(0.5)
    
    return Response(generate(), mimetype='text/event-stream')

@app.route("/console/<name>/input", methods=["POST"])
@login_required
def console_input(name):
    user = session['username']
    key = (user, name)
    data = request.json
    command = data.get('command', '')
    
    if key in processes:
        p = processes[key]
        try:
            p.stdin.write(command + '\n')
            p.stdin.flush()
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    return jsonify({"success": False, "error": "Process not running"})

@app.route("/edit/<name>")
@login_required
def edit_files(name):
    user = session['username']
    app_dir = os.path.join(UPLOAD_FOLDER, user, name, "extracted")
    
    files = []
    if os.path.exists(app_dir):
        for root, dirs, filenames in os.walk(app_dir):
            for filename in filenames:
                if filename.endswith(('.py', '.txt', '.json', '.env', '.md', '.yml', '.yaml', '.cfg', '.ini')):
                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, app_dir)
                    files.append(rel_path)
    
    return render_template_string(EDIT_TEMPLATE, bot_name=name, files=files)

@app.route("/edit/<name>/file")
@login_required
def get_file_content(name):
    user = session['username']
    filepath = request.args.get('path', '')
    filepath = filepath.replace('..', '').replace('//', '/')
    full_path = os.path.join(UPLOAD_FOLDER, user, name, "extracted", filepath)
    
    if os.path.exists(full_path) and os.path.isfile(full_path):
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({"success": True, "content": content})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    return jsonify({"success": False, "error": "File not found"})

@app.route("/edit/<name>/save", methods=["POST"])
@login_required
def save_file_content(name):
    user = session['username']
    data = request.json
    filepath = data.get('path', '')
    content = data.get('content', '')
    
    filepath = filepath.replace('..', '').replace('//', '/')
    full_path = os.path.join(UPLOAD_FOLDER, user, name, "extracted", filepath)
    
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/pricing")
@login_required
def pricing():
    plans = load_plans()
    user_sub = get_user_subscription(session['username'])
    return render_template_string(PRICING_TEMPLATE, plans=plans, current_plan=user_sub["plan"])

@app.route("/purchase/<plan_id>", methods=["POST"])
@login_required
def purchase_plan(plan_id):
    user = session['username']
    plans = load_plans()
    
    if plan_id not in plans or not plans[plan_id]["active"]:
        flash("Invalid plan selected", "error")
        return redirect(url_for("pricing"))
    
    plan = plans[plan_id]
    
    if plan["price"] == 0:
        subs = load_subscriptions()
        subs[user] = {
            "plan": plan_id,
            "expires": None,
            "active": True,
            "purchased_at": datetime.datetime.now().isoformat()
        }
        save_subscriptions(subs)
        flash(f"Successfully subscribed to {plan['name']} plan!", "success")
        return redirect(url_for("dashboard"))
    
    payment_id = str(uuid.uuid4())
    
    payments = load_payments()
    payments[payment_id] = {
        "user": user,
        "plan": plan_id,
        "amount": plan["price"],
        "status": "pending",
        "created_at": datetime.datetime.now().isoformat(),
        "payment_method": "manual"
    }
    save_payments(payments)
    
    subs = load_subscriptions()
    subs[user] = {
        "plan": plan_id,
        "expires": (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat(),
        "active": True,
        "purchased_at": datetime.datetime.now().isoformat(),
        "payment_id": payment_id
    }
    save_subscriptions(subs)
    
    payments[payment_id]["status"] = "completed"
    save_payments(payments)
    
    flash(f"Successfully upgraded to {plan['name']} plan!", "success")
    return redirect(url_for("dashboard"))

# ---------- Admin Routes ----------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for("admin_dashboard"))
    
    if request.method == "POST":
        u = request.form.get("u", "").strip()
        p = request.form.get("p", "").strip()
        
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session.clear()
            session['username'] = ADMIN_USERNAME
            session['is_admin'] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template_string(ADMIN_LOGIN_TEMPLATE, error="Invalid credentials")
    
    return render_template_string(ADMIN_LOGIN_TEMPLATE, error=None)

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    users = load_users()
    subs = load_subscriptions()
    payments = load_payments()
    plans = load_plans()
    
    total_users = len(users)
    total_revenue = sum(p["amount"] for p in payments.values() if p["status"] == "completed")
    active_subs = sum(1 for s in subs.values() if s["active"])
    
    bots_list = []
    for u_name in os.listdir(UPLOAD_FOLDER):
        u_path = os.path.join(UPLOAD_FOLDER, u_name)
        if os.path.isdir(u_path):
            for a_name in os.listdir(u_path):
                if os.path.isdir(os.path.join(u_path, a_name)):
                    is_running = (u_name, a_name) in processes
                    user_plan = subs.get(u_name, {}).get('plan', 'starter')
                    plan_name = plans.get(user_plan, {}).get('name', 'Starter')
                    bots_list.append({
                        'user': u_name,
                        'name': a_name,
                        'running': is_running,
                        'plan': plan_name
                    })
    
    messages = get_flashed_messages(with_categories=True)
    
    return render_template_string(ADMIN_DASHBOARD_TEMPLATE,
                         users=users,
                         subs=subs,
                         payments=payments,
                         plans=plans,
                         bots_list=bots_list,
                         stats={
                             "total_users": total_users,
                             "total_revenue": total_revenue,
                             "active_subs": active_subs
                         },
                         messages=messages)

@app.route("/admin/plans", methods=["GET", "POST"])
@admin_required
def admin_plans():
    plans = load_plans()
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "create":
            plan_id = request.form.get("plan_id", "").lower().replace(" ", "_")
            if plan_id and plan_id not in plans:
                plans[plan_id] = {
                    "id": plan_id,
                    "name": request.form.get("name"),
                    "price": float(request.form.get("price", 0)),
                    "ram": request.form.get("ram"),
                    "storage": request.form.get("storage"),
                    "bots": int(request.form.get("bots", 1)),
                    "features": [f.strip() for f in request.form.get("features", "").split(",") if f.strip()],
                    "popular": request.form.get("popular") == "on",
                    "active": True
                }
                save_plans(plans)
                flash("Plan created successfully!", "success")
    
    messages = get_flashed_messages(with_categories=True)
    return render_template_string(ADMIN_PLANS_TEMPLATE, plans=plans, messages=messages)

@app.route("/admin/users")
@admin_required
def admin_users():
    users = load_users()
    subs = load_subscriptions()
    plans = load_plans()
    return render_template_string(ADMIN_USERS_TEMPLATE, users=users, subs=subs, plans=plans)

@app.route("/admin/user/<username>/setplan", methods=["POST"])
@admin_required
def admin_set_user_plan(username):
    plan_id = request.form.get("plan_id")
    plans = load_plans()
    
    if plan_id in plans:
        subs = load_subscriptions()
        subs[username] = {
            "plan": plan_id,
            "expires": None,
            "active": True,
            "purchased_at": datetime.datetime.now().isoformat(),
            "manual_override": True
        }
        save_subscriptions(subs)
        flash(f"Updated {username}'s plan to {plans[plan_id]['name']}", "success")
    
    return redirect(url_for("admin_users"))

@app.route("/admin/payments")
@admin_required
def admin_payments():
    payments = load_payments()
    users = load_users()
    return render_template_string(ADMIN_PAYMENTS_TEMPLATE, payments=payments, users=users)

@app.route("/admin/download/<user>/<name>")
@admin_required
def admin_download(user, name):
    path = os.path.join(UPLOAD_FOLDER, user, name, "app.zip")
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "Not Found", 404

@app.route("/admin/run/<user>/<name>")
@admin_required
def admin_run(user, name):
    success, msg = start_app(user, name)
    if success:
        flash(f"Started {user}/{name}", "success")
    else:
        flash(f"Failed: {msg}", "error")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/stop/<user>/<name>")
@admin_required
def admin_stop(user, name):
    if stop_app(user, name):
        flash(f"Stopped {user}/{name}", "success")
    else:
        flash(f"{user}/{name} was not running", "error")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/restart/<user>/<name>")
@admin_required
def admin_restart(user, name):
    success, msg = restart_app(user, name)
    if success:
        flash(f"Restarted {user}/{name}", "success")
    else:
        flash(f"Failed to restart: {msg}", "error")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete/<user>/<name>")
@admin_required
def admin_delete(user, name):
    stop_app(user, name)
    shutil.rmtree(os.path.join(UPLOAD_FOLDER, user, name), ignore_errors=True)
    flash(f"Deleted {user}/{name}", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

# ---------- HTML TEMPLATES ----------
LANDING_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BLACK ADMIN HOSTING PANEL</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: #0a0a0a;
            color: #ffffff;
            overflow-x: hidden;
        }
        nav {
            position: fixed;
            top: 0;
            width: 100%;
            padding: 20px 50px;
            background: rgba(10, 10, 10, 0.8);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            z-index: 1000;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo {
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: -1px;
        }
        .nav-links {
            display: flex;
            gap: 30px;
            align-items: center;
        }
        .nav-links a {
            color: #a0a0a0;
            text-decoration: none;
            font-weight: 500;
            transition: color 0.3s;
        }
        .nav-links a:hover { color: #00ffcc; }
        .login-btn {
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000 !important;
            padding: 10px 25px;
            border-radius: 25px;
            font-weight: 600;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 255, 204, 0.3);
        }
        .hero {
            margin-top: 80px;
            padding: 100px 50px;
            text-align: center;
            background: radial-gradient(ellipse at top, rgba(0, 255, 204, 0.1), transparent 50%),
                        radial-gradient(ellipse at bottom, rgba(0, 212, 255, 0.1), transparent 50%);
        }
        .hero h1 {
            font-size: 72px;
            font-weight: 800;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #ffffff, #00ffcc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1.1;
        }
        .hero p {
            font-size: 20px;
            color: #a0a0a0;
            max-width: 600px;
            margin: 0 auto 40px;
            line-height: 1.6;
        }
        .cta-buttons {
            display: flex;
            gap: 20px;
            justify-content: center;
            margin-bottom: 60px;
        }
        .btn-primary {
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000;
            padding: 15px 40px;
            border-radius: 30px;
            text-decoration: none;
            font-weight: 700;
            font-size: 16px;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(0, 255, 204, 0.3);
        }
        .btn-primary:hover {
            transform: translateY(-3px);
            box-shadow: 0 20px 40px rgba(0, 255, 204, 0.4);
        }
        .btn-secondary {
            background: transparent;
            color: #fff;
            padding: 15px 40px;
            border-radius: 30px;
            text-decoration: none;
            font-weight: 600;
            font-size: 16px;
            border: 2px solid rgba(255, 255, 255, 0.2);
            transition: all 0.3s;
        }
        .btn-secondary:hover {
            border-color: #00ffcc;
            color: #00ffcc;
        }
        .stats {
            display: flex;
            justify-content: center;
            gap: 60px;
            flex-wrap: wrap;
            margin-top: 40px;
        }
        .stat-item { text-align: center; }
        .stat-number {
            font-size: 48px;
            font-weight: 800;
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .stat-label {
            color: #666;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 5px;
        }
        .pricing-section {
            padding: 100px 50px;
            background: radial-gradient(ellipse at center, rgba(0, 255, 204, 0.05), transparent 70%);
        }
        .section-title {
            text-align: center;
            font-size: 42px;
            font-weight: 700;
            margin-bottom: 60px;
            color: #fff;
        }
        .pricing-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 30px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .pricing-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 40px;
            position: relative;
            transition: all 0.3s;
        }
        .pricing-card:hover { transform: scale(1.02); }
        .pricing-card.popular {
            border-color: #00ffcc;
            background: rgba(0, 255, 204, 0.05);
        }
        .popular-badge {
            position: absolute;
            top: -12px;
            right: 20px;
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
        }
        .pricing-card h3 {
            font-size: 24px;
            margin-bottom: 10px;
        }
        .price {
            font-size: 48px;
            font-weight: 800;
            margin-bottom: 30px;
        }
        .price span {
            font-size: 16px;
            color: #666;
            font-weight: 400;
        }
        .features-list {
            list-style: none;
            margin-bottom: 30px;
        }
        .features-list li {
            padding: 10px 0;
            color: #aaa;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        .features-list li:before {
            content: "✓";
            color: #00ffcc;
            margin-right: 10px;
            font-weight: bold;
        }
        footer {
            padding: 50px;
            text-align: center;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            color: #666;
        }
    </style>
</head>
<body>
    <nav>
        <div class="logo">⚡ BLACK ADMIN</div>
        <div class="nav-links">
            <a href="#pricing">Pricing</a>
            <a href="/login" class="login-btn">Login</a>
        </div>
    </nav>

    <section class="hero">
        <h1>Host Your Bots<br>With Power</h1>
        <p>Deploy your Discord bots and applications with ultra-low latency, DDoS protection, and 24/7 uptime.</p>
        <div class="cta-buttons">
            <a href="/login" class="btn-primary">Get Started Free</a>
            <a href="#pricing" class="btn-secondary">View Plans</a>
        </div>
        <div class="stats">
            <div class="stat-item">
                <div class="stat-number">100K+</div>
                <div class="stat-label">Active Users</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">99.9%</div>
                <div class="stat-label">Uptime</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">24/7</div>
                <div class="stat-label">Support</div>
            </div>
        </div>
    </section>

    <section class="pricing-section" id="pricing">
        <h2 class="section-title">Choose Your Plan</h2>
        <div class="pricing-grid">
            {% for plan_id, plan in plans.items() if plan.active %}
            <div class="pricing-card {% if plan.popular %}popular{% endif %}">
                {% if plan.popular %}<div class="popular-badge">POPULAR</div>{% endif %}
                <h3>{{ plan.name }}</h3>
                <div class="price">${{ plan.price }}<span>/month</span></div>
                <ul class="features-list">
                    <li>{{ plan.ram }} RAM</li>
                    <li>{{ plan.storage }} Storage</li>
                    <li>{{ plan.bots }} Bot Slots</li>
                    {% for feature in plan.features %}
                    <li>{{ feature }}</li>
                    {% endfor %}
                </ul>
                <a href="/login" class="btn-primary" style="width: 100%; display: inline-block; text-align: center;">
                    {% if plan.price == 0 %}Get Started{% else %}Upgrade{% endif %}
                </a>
            </div>
            {% endfor %}
        </div>
    </section>

    <footer>
        <p>&copy; 2026 BLACK ADMIN HOSTING PANEL. All rights reserved.</p>
    </footer>
</body>
</html>
'''

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>BLACK ADMIN HOSTING - Login</title>
    <style>
        body {
            background: #050505;
            color: white;
            text-align: center;
            padding-top: 100px;
            font-family: sans-serif;
            overflow: hidden;
        }
        .container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 25px 45px rgba(0,0,0,0.5), inset 0 0 15px rgba(0,255,204,0.2);
            border-radius: 20px;
            padding: 50px;
            display: inline-block;
            transform: perspective(1000px) rotateX(5deg);
            animation: glow 3s infinite alternate;
        }
        @keyframes glow { 
            from { box-shadow: 0 0 10px #00ffcc; } 
            to { box-shadow: 0 0 30px #00ffcc; } 
        }
        input {
            background: rgba(255,255,255,0.1);
            border: none;
            outline: none;
            padding: 15px;
            margin: 10px;
            color: white;
            border-radius: 10px;
            width: 280px;
            box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5);
        }
        button {
            background: #00ffcc;
            color: black;
            font-weight: bold;
            padding: 15px 40px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: 0.3s;
            box-shadow: 0 5px 15px rgba(0,255,204,0.4);
        }
        button:hover { 
            transform: scale(1.05); 
            box-shadow: 0 0 25px #00ffcc; 
        }
        .error {
            color: #ff4444;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color:#00ffcc; text-shadow: 0 0 10px #00ffcc;">BLACK ADMIN HOSTING PANEL</h2>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <form method="post">
            <input type="text" name="username" placeholder="Username" required><br>
            <input type="text" name="access_key" placeholder="Password" required><br><br>
            <button type="submit">LOGIN SYSTEM</button>
        </form>
        <p style="margin-top: 20px; color: #666; font-size: 12px;">
            New user? Just enter username/password to auto-register
        </p>
    </div>
</body>
</html>
'''

DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - BLACK ADMIN</title>
    <style>
        body {
            background: #0a0a0a;
            color: white;
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
        }
        .logo {
            font-size: 24px;
            font-weight: 800;
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .nav a {
            color: #00ffcc;
            text-decoration: none;
            margin-left: 20px;
        }
        .plan-badge {
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 12px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-box {
            background: rgba(255,255,255,0.05);
            padding: 20px;
            border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stat-label { color: #666; font-size: 12px; }
        .stat-value { font-size: 24px; font-weight: 700; margin-top: 5px; }
        .upload-section {
            background: rgba(255,255,255,0.05);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
        }
        .btn {
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000;
            padding: 12px 30px;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
            margin: 5px;
        }
        .btn-danger {
            background: linear-gradient(135deg, #ff4444, #ff8844);
        }
        .btn-warning {
            background: linear-gradient(135deg, #ffaa00, #ffcc00);
            color: #000;
        }
        .btn-info {
            background: linear-gradient(135deg, #00d4ff, #0088ff);
        }
        .apps-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .app-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
        }
        .app-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .status {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
        }
        .status.running { background: #00ffcc; box-shadow: 0 0 10px #00ffcc; }
        .status.stopped { background: #ff4444; }
        .logs {
            background: #000;
            padding: 15px;
            border-radius: 10px;
            font-family: monospace;
            font-size: 12px;
            max-height: 150px;
            overflow-y: auto;
            color: #888;
            white-space: pre-wrap;
        }
        .actions {
            margin-top: 15px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .actions a {
            color: #00ffcc;
            text-decoration: none;
            font-size: 14px;
            padding: 8px 15px;
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            transition: all 0.3s;
        }
        .actions a:hover {
            background: rgba(0,255,204,0.2);
        }
        .flash {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .flash.error { background: rgba(255,68,68,0.2); border: 1px solid #ff4444; color: #ff4444; }
        .flash.success { background: rgba(0,255,204,0.2); border: 1px solid #00ffcc; color: #00ffcc; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">⚡ BLACK ADMIN</div>
        <div>
            <span class="plan-badge">{{ current_plan.name }} PLAN</span>
            <span style="margin-left: 20px; color: #666;">{{ session.username }}</span>
            <a href="/logout" style="color: #ff4444; margin-left: 20px; text-decoration: none;">Logout</a>
        </div>
    </div>

    {% if messages %}
        {% for category, message in messages %}
            <div class="flash {{ category }}">{{ message }}</div>
        {% endfor %}
    {% endif %}

    <div class="stats">
        <div class="stat-box">
            <div class="stat-label">PLAN</div>
            <div class="stat-value" style="color: #00ffcc;">{{ current_plan.name }}</div>
        </div>
        <div class="stat-box">
            <div class="stat-label">BOTS</div>
            <div class="stat-value">{{ app_count }} / {{ limits.max_bots }}</div>
        </div>
        <div class="stat-box">
            <div class="stat-label">RAM</div>
            <div class="stat-value">{{ limits.ram }}</div>
        </div>
        <div class="stat-box">
            <div class="stat-label">STORAGE</div>
            <div class="stat-value">{{ limits.storage }}</div>
        </div>
    </div>

    <div class="upload-section">
        <h3 style="margin-bottom: 20px;">Upload New Bot</h3>
        <form method="post" action="/upload" enctype="multipart/form-data">
            <input type="file" name="file" accept=".zip" required style="margin-bottom: 15px; color: white;">
            <br>
            <button type="submit" class="btn">Upload ZIP File</button>
        </form>
        <p style="color: #666; margin-top: 15px; font-size: 12px;">
            Upload your bot as a ZIP file containing main.py/app.py/bot.py
        </p>
    </div>

    <h3 style="margin-bottom: 20px;">Your Bots</h3>
    <div class="apps-grid">
        {% for app in apps %}
        <div class="app-card">
            <div class="app-header">
                <h4>{{ app.name }}</h4>
                <span class="status {% if app.running %}running{% else %}stopped{% endif %}"></span>
            </div>
            <div class="logs">{{ app.log }}</div>
            <div class="actions">
                {% if app.running %}
                    <a href="/stop/{{ app.name }}" style="color: #ffaa00;">⏹ Stop</a>
                    <a href="/restart/{{ app.name }}" style="color: #00d4ff;">🔄 Restart</a>
                {% else %}
                    <a href="/run/{{ app.name }}" style="color: #00ffcc;">▶ Run</a>
                {% endif %}
                <a href="/console/{{ app.name }}" style="color: #00d4ff;">💻 Console</a>
                <a href="/edit/{{ app.name }}" style="color: #aa88ff;">✏ Edit</a>
                <a href="/delete/{{ app.name }}" style="color: #ff4444;" onclick="return confirm('Delete this bot?')">🗑 Delete</a>
            </div>
        </div>
        {% else %}
        <div style="color: #666; text-align: center; grid-column: 1/-1;">
            No bots uploaded yet. Upload your first bot above!
        </div>
        {% endfor %}
    </div>

    <div style="text-align: center; margin-top: 30px;">
        <a href="/pricing" class="btn">Upgrade Plan</a>
    </div>
</body>
</html>
'''

CONSOLE_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Console - {{ bot_name }}</title>
    <style>
        body {
            background: #0a0a0a;
            color: white;
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            flex-shrink: 0;
        }
        .logo {
            font-size: 24px;
            font-weight: 800;
            color: #00ffcc;
        }
        .status {
            padding: 8px 20px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
        }
        .status.running { background: rgba(0,255,204,0.2); color: #00ffcc; }
        .status.stopped { background: rgba(255,68,68,0.2); color: #ff4444; }
        #console {
            background: #000;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 25px;
            flex: 1;
            overflow-y: auto;
            font-size: 16px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
            margin-bottom: 15px;
            min-height: 600px;
        }
        .input-line {
            display: flex;
            gap: 15px;
            flex-shrink: 0;
            padding: 10px 0;
        }
        #commandInput {
            flex: 1;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            font-family: inherit;
            font-size: 16px;
        }
        button {
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000;
            border: none;
            padding: 15px 35px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 700;
            font-size: 16px;
            transition: transform 0.2s;
        }
        button:hover {
            transform: scale(1.05);
        }
        button:disabled {
            background: #333;
            color: #666;
            cursor: not-allowed;
            transform: none;
        }
        .back {
            color: #666;
            text-decoration: none;
            font-size: 16px;
            padding: 10px 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            transition: all 0.3s;
        }
        .back:hover {
            background: rgba(255,255,255,0.1);
            color: #00ffcc;
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <span class="logo">💻 Console: {{ bot_name }}</span>
            <span class="status {% if running %}running{% else %}stopped{% endif %}" style="margin-left: 20px;">
                {% if running %}RUNNING{% else %}STOPPED{% endif %}
            </span>
        </div>
        <a href="/dashboard" class="back">← Back to Dashboard</a>
    </div>

    <div id="console">{{ output }}</div>
    
    <div class="input-line">
        <input type="text" id="commandInput" placeholder="Enter command..." {% if not running %}disabled{% endif %}>
        <button onclick="sendCommand()" {% if not running %}disabled{% endif %}>Send Command</button>
    </div>

    <script>
        const consoleDiv = document.getElementById('console');
        const input = document.getElementById('commandInput');
        
        consoleDiv.scrollTop = consoleDiv.scrollHeight;
        
        {% if running %}
        const evtSource = new EventSource('/console/{{ bot_name }}/stream');
        evtSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            data.lines.forEach(line => {
                const div = document.createElement('div');
                div.textContent = line;
                consoleDiv.appendChild(div);
            });
            consoleDiv.scrollTop = consoleDiv.scrollHeight;
        };
        {% endif %}
        
        function sendCommand() {
            const cmd = input.value;
            if (!cmd) return;
            
            fetch('/console/{{ bot_name }}/input', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: cmd})
            });
            
            const div = document.createElement('div');
            div.style.color = '#00ffcc';
            div.style.fontWeight = 'bold';
            div.textContent = '> ' + cmd;
            consoleDiv.appendChild(div);
            
            input.value = '';
            consoleDiv.scrollTop = consoleDiv.scrollHeight;
        }
        
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendCommand();
        });
    </script>
</body>
</html>
'''

EDIT_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Edit Files - {{ bot_name }}</title>
    <style>
        body {
            background: #0a0a0a;
            color: white;
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
        }
        .logo {
            font-size: 20px;
            font-weight: 800;
            color: #aa88ff;
        }
        .container {
            display: grid;
            grid-template-columns: 250px 1fr;
            gap: 20px;
            height: calc(100vh - 150px);
        }
        .file-list {
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 15px;
            overflow-y: auto;
        }
        .file-item {
            padding: 10px;
            cursor: pointer;
            border-radius: 5px;
            margin-bottom: 5px;
            transition: all 0.3s;
        }
        .file-item:hover {
            background: rgba(255,255,255,0.1);
        }
        .file-item.active {
            background: rgba(170,136,255,0.3);
        }
        .editor {
            display: flex;
            flex-direction: column;
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 15px;
        }
        #editor {
            flex: 1;
            background: #000;
            border: 1px solid rgba(255,255,255,0.2);
            color: #00ffcc;
            padding: 15px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            border-radius: 5px;
            resize: none;
            outline: none;
        }
        .toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .filename {
            color: #aa88ff;
            font-weight: 600;
        }
        button {
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000;
            border: none;
            padding: 10px 25px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 600;
        }
        button:disabled {
            background: #333;
            color: #666;
        }
        .back {
            color: #666;
            text-decoration: none;
        }
        .message {
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
            display: none;
        }
        .message.success {
            background: rgba(0,255,204,0.2);
            border: 1px solid #00ffcc;
            display: block;
        }
        .message.error {
            background: rgba(255,68,68,0.2);
            border: 1px solid #ff4444;
            display: block;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">✏️ Edit: {{ bot_name }}</div>
        <a href="/dashboard" class="back">← Back to Dashboard</a>
    </div>

    <div id="message" class="message"></div>

    <div class="container">
        <div class="file-list">
            <h4 style="margin-bottom: 15px; color: #666;">Files</h4>
            {% for file in files %}
            <div class="file-item" onclick="loadFile('{{ file }}')">{{ file }}</div>
            {% endfor %}
        </div>
        
        <div class="editor">
            <div class="toolbar">
                <span class="filename" id="currentFile">Select a file</span>
                <button onclick="saveFile()" id="saveBtn" disabled>💾 Save</button>
            </div>
            <textarea id="editor" placeholder="Select a file to edit..." disabled></textarea>
        </div>
    </div>

    <script>
        let currentFile = '';
        const editor = document.getElementById('editor');
        const saveBtn = document.getElementById('saveBtn');
        const currentFileSpan = document.getElementById('currentFile');
        const messageDiv = document.getElementById('message');
        
        function loadFile(filepath) {
            currentFile = filepath;
            currentFileSpan.textContent = filepath;
            
            document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
            event.target.classList.add('active');
            
            fetch(`/edit/{{ bot_name }}/file?path=${encodeURIComponent(filepath)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        editor.value = data.content;
                        editor.disabled = false;
                        saveBtn.disabled = false;
                    } else {
                        showMessage(data.error, 'error');
                    }
                });
        }
        
        function saveFile() {
            if (!currentFile) return;
            
            fetch(`/edit/{{ bot_name }}/save`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    path: currentFile,
                    content: editor.value
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    showMessage('File saved successfully!', 'success');
                } else {
                    showMessage(data.error, 'error');
                }
            });
        }
        
        function showMessage(text, type) {
            messageDiv.textContent = text;
            messageDiv.className = `message ${type}`;
            setTimeout(() => messageDiv.className = 'message', 3000);
        }
        
        editor.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                saveFile();
            }
        });
    </script>
</body>
</html>
'''

PRICING_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Pricing - BLACK ADMIN</title>
    <style>
        body {
            background: #0a0a0a;
            color: white;
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 40px;
        }
        .header {
            text-align: center;
            margin-bottom: 50px;
        }
        .logo {
            font-size: 32px;
            font-weight: 800;
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .pricing-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .pricing-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 40px;
            text-align: center;
            position: relative;
            transition: transform 0.3s;
        }
        .pricing-card:hover { transform: translateY(-5px); }
        .pricing-card.current {
            border-color: #00ffcc;
            box-shadow: 0 0 30px rgba(0,255,204,0.2);
        }
        .pricing-card.popular {
            border-color: #00d4ff;
            background: rgba(0,212,255,0.05);
        }
        .badge {
            position: absolute;
            top: -10px;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000;
            padding: 5px 20px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
        }
        h2 { margin-bottom: 10px; }
        .price {
            font-size: 48px;
            font-weight: 800;
            margin: 20px 0;
        }
        .price span { font-size: 16px; color: #666; }
        .features {
            list-style: none;
            margin: 30px 0;
            text-align: left;
        }
        .features li {
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .features li:before {
            content: "✓";
            color: #00ffcc;
            margin-right: 10px;
        }
        .btn {
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000;
            padding: 15px 40px;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-weight: 700;
            width: 100%;
            font-size: 16px;
        }
        .btn:disabled {
            background: #333;
            color: #666;
            cursor: not-allowed;
        }
        .back {
            display: inline-block;
            margin-top: 40px;
            color: #666;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">⚡ BLACK ADMIN</div>
        <h1 style="margin-top: 20px;">Upgrade Your Plan</h1>
        <p style="color: #666;">Choose the perfect plan for your needs</p>
    </div>

    <div class="pricing-grid">
        {% for plan_id, plan in plans.items() if plan.active %}
        <div class="pricing-card {% if plan_id == current_plan %}current{% endif %} {% if plan.popular %}popular{% endif %}">
            {% if plan_id == current_plan %}<div class="badge">CURRENT</div>{% endif %}
            {% if plan.popular and plan_id != current_plan %}<div class="badge">POPULAR</div>{% endif %}
            
            <h2>{{ plan.name }}</h2>
            <div class="price">${{ plan.price }}<span>/month</span></div>
            
            <ul class="features">
                <li>{{ plan.ram }} RAM</li>
                <li>{{ plan.storage }} Storage</li>
                <li>{{ plan.bots }} Bot Slot{% if plan.bots > 1 %}s{% endif %}</li>
                {% for feature in plan.features %}
                <li>{{ feature }}</li>
                {% endfor %}
            </ul>

            <form method="post" action="/purchase/{{ plan_id }}">
                <button type="submit" class="btn" {% if plan_id == current_plan %}disabled{% endif %}>
                    {% if plan_id == current_plan %}Current Plan{% elif plan.price == 0 %}Select Free{% else %}Upgrade Now{% endif %}
                </button>
            </form>
        </div>
        {% endfor %}
    </div>

    <div style="text-align: center;">
        <a href="/dashboard" class="back">← Back to Dashboard</a>
    </div>
</body>
</html>
'''

ADMIN_LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login - BLACK ADMIN</title>
    <style>
        body {
            background: #050505;
            color: white;
            text-align: center;
            padding-top: 100px;
            font-family: sans-serif;
            margin: 0;
        }
        .glow-box {
            background: rgba(0, 0, 0, 0.6);
            border: 2px solid #fff;
            padding: 60px;
            border-radius: 30px;
            display: inline-block;
            animation: adminGlow 2s infinite alternate;
            transform: perspective(1000px) rotateY(10deg);
        }
        @keyframes adminGlow { 
            from { box-shadow: 0 0 20px #ff00de; } 
            to { box-shadow: 0 0 50px #00d4ff; } 
        }
        input { 
            padding: 12px; 
            margin: 10px; 
            width: 250px; 
            border-radius: 8px; 
            border: 1px solid #fff; 
            background: transparent; 
            color: #fff; 
            font-size: 16px;
        }
        button { 
            padding: 15px 50px; 
            background: linear-gradient(45deg, #ff00de, #00d4ff); 
            border: none; 
            color: white; 
            border-radius: 10px; 
            cursor: pointer; 
            font-weight: bold; 
            margin-top: 20px;
            font-size: 16px;
        }
        button:hover {
            transform: scale(1.05);
        }
        .error {
            color: #ff4444;
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="glow-box">
        <h1 style="text-shadow: 0 0 15px #00d4ff;">🛡️ MASTER CONTROL</h1>
        <p style="color: #888; margin-bottom: 30px;">BLACK ADMIN HOSTING</p>
        
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        
        <form method="post">
            <input type="text" name="u" placeholder="Username" required><br>
            <input type="password" name="p" placeholder="Password" required><br>
            <button type="submit">UNLOCK ADMIN PANEL</button>
        </form>
    </div>
</body>
</html>
'''

ADMIN_DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard - BLACK ADMIN</title>
    <style>
        body {
            background: #0a0a0a;
            color: white;
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 40px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
        }
        .logo {
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(135deg, #ff00de, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .nav a {
            color: #00d4ff;
            text-decoration: none;
            margin-left: 20px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .stat-card {
            background: rgba(255,255,255,0.05);
            padding: 30px;
            border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stat-value {
            font-size: 36px;
            font-weight: 800;
            color: #00ffcc;
        }
        .stat-label { color: #666; margin-top: 5px; }
        table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(255,255,255,0.02);
            border-radius: 15px;
            overflow: hidden;
            margin-top: 20px;
        }
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th {
            background: rgba(255,255,255,0.05);
            color: #00ffcc;
        }
        .status {
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .status.running { background: rgba(0,255,204,0.2); color: #00ffcc; }
        .status.stopped { background: rgba(255,68,68,0.2); color: #ff4444; }
        a { color: #00d4ff; text-decoration: none; }
        .actions a { 
            margin-right: 10px; 
            padding: 10px 18px; 
            background: rgba(255,255,255,0.1); 
            border-radius: 8px; 
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s;
            display: inline-block;
        }
        .actions a:hover { 
            background: rgba(0,255,204,0.3); 
            transform: translateY(-2px);
        }
        .menu {
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
        }
        .menu a {
            padding: 12px 25px;
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            transition: all 0.3s;
            font-weight: 600;
        }
        .menu a:hover { 
            background: rgba(0,255,204,0.2); 
            transform: translateY(-2px);
        }
        .flash {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .flash.success { background: rgba(0,255,204,0.2); border: 1px solid #00ffcc; color: #00ffcc; }
        .flash.error { background: rgba(255,68,68,0.2); border: 1px solid #ff4444; color: #ff4444; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🛡️ BLACK ADMIN PANEL</div>
        <div class="nav">
            <span style="color: #666;">Master Admin</span>
            <a href="/logout">Logout</a>
        </div>
    </div>

    {% if messages %}
        {% for category, message in messages %}
            <div class="flash {{ category }}">{{ message }}</div>
        {% endfor %}
    {% endif %}

    <div class="menu">
        <a href="/admin/dashboard">Dashboard</a>
        <a href="/admin/plans">Manage Plans</a>
        <a href="/admin/users">Users</a>
        <a href="/admin/payments">Payments</a>
    </div>

    <div class="stats">
        <div class="stat-card">
            <div class="stat-value">{{ stats.total_users }}</div>
            <div class="stat-label">Total Users</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${{ "%.2f"|format(stats.total_revenue) }}</div>
            <div class="stat-label">Total Revenue</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ stats.active_subs }}</div>
            <div class="stat-label">Active Subscriptions</div>
        </div>
    </div>

    <h3 style="margin-bottom: 20px;">All Bots</h3>
    <table>
        <tr>
            <th>User</th>
            <th>Bot Name</th>
            <th>Status</th>
            <th>Plan</th>
            <th>Actions</th>
        </tr>
        {% for bot in bots_list %}
        <tr>
            <td>{{ bot.user }}</td>
            <td>{{ bot.name }}</td>
            <td>
                {% if bot.running %}
                    <span class="status running">RUNNING</span>
                {% else %}
                    <span class="status stopped">STOPPED</span>
                {% endif %}
            </td>
            <td>{{ bot.plan }}</td>
            <td class="actions">
                <a href="/admin/run/{{ bot.user }}/{{ bot.name }}" style="color: lime;">▶ Run</a>
                <a href="/admin/stop/{{ bot.user }}/{{ bot.name }}" style="color: orange;">⏹ Stop</a>
                <a href="/admin/restart/{{ bot.user }}/{{ bot.name }}" style="color: #00d4ff;">🔄 Restart</a>
                <a href="/admin/delete/{{ bot.user }}/{{ bot.name }}" style="color: red;">🗑 Delete</a>
                <a href="/admin/download/{{ bot.user }}/{{ bot.name }}" style="color: cyan;">⬇ Download</a>
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
'''

ADMIN_PLANS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Manage Plans - BLACK ADMIN</title>
    <style>
        body {
            background: #0a0a0a;
            color: white;
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 40px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
        }
        .logo {
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(135deg, #ff00de, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .nav a {
            color: #00d4ff;
            text-decoration: none;
            margin-left: 20px;
        }
        .plans-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .plan-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            position: relative;
        }
        .plan-card.inactive { opacity: 0.5; }
        .plan-card h3 {
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .badge {
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000;
            padding: 3px 10px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 700;
        }
        .price {
            font-size: 32px;
            font-weight: 800;
            color: #00ffcc;
            margin-bottom: 15px;
        }
        .features {
            list-style: none;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .features li {
            padding: 5px 0;
            color: #aaa;
        }
        .btn {
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000;
            padding: 8px 20px;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-weight: 600;
            margin-right: 10px;
        }
        .create-form {
            background: rgba(255,255,255,0.05);
            padding: 30px;
            border-radius: 15px;
            max-width: 600px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #aaa;
        }
        input, select {
            width: 100%;
            padding: 10px;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            color: white;
        }
        .checkbox-group {
            display: flex;
            gap: 20px;
            margin-top: 10px;
        }
        .flash {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .flash.success { background: rgba(0,255,204,0.2); border: 1px solid #00ffcc; color: #00ffcc; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🛡️ MANAGE PLANS</div>
        <div class="nav">
            <a href="/admin/dashboard">Dashboard</a>
            <a href="/logout">Logout</a>
        </div>
    </div>

    {% if messages %}
        {% for category, message in messages %}
            <div class="flash {{ category }}">{{ message }}</div>
        {% endfor %}
    {% endif %}

    <h3 style="margin-bottom: 20px;">Existing Plans (Cannot Delete)</h3>
    <div class="plans-grid">
        {% for plan_id, plan in plans.items() %}
        <div class="plan-card {% if not plan.active %}inactive{% endif %}">
            <h3>
                {{ plan.name }}
                {% if plan.popular %}<span class="badge">POPULAR</span>{% endif %}
                {% if not plan.active %}<span class="badge" style="background: #ff4444; color: white;">INACTIVE</span>{% endif %}
            </h3>
            <div class="price">${{ plan.price }}/mo</div>
            <ul class="features">
                <li>{{ plan.ram }} RAM</li>
                <li>{{ plan.storage }} Storage</li>
                <li>{{ plan.bots }} Bots</li>
                <li>{{ plan.features|join(', ') }}</li>
            </ul>
        </div>
        {% endfor %}
    </div>

    <h3 style="margin-bottom: 20px;">Create New Plan</h3>
    <div class="create-form">
        <form method="post">
            <input type="hidden" name="action" value="create">
            
            <div class="form-group">
                <label>Plan ID (unique, lowercase)</label>
                <input type="text" name="plan_id" placeholder="e.g., premium" required>
            </div>
            
            <div class="form-group">
                <label>Plan Name</label>
                <input type="text" name="name" placeholder="e.g., Premium" required>
            </div>
            
            <div class="form-group">
                <label>Price ($/month)</label>
                <input type="number" name="price" step="0.01" value="0" required>
            </div>
            
            <div class="form-group">
                <label>RAM</label>
                <input type="text" name="ram" placeholder="e.g., 4 GB" required>
            </div>
            
            <div class="form-group">
                <label>Storage</label>
                <input type="text" name="storage" placeholder="e.g., 20 GB" required>
            </div>
            
            <div class="form-group">
                <label>Max Bots</label>
                <input type="number" name="bots" value="1" required>
            </div>
            
            <div class="form-group">
                <label>Features (comma separated)</label>
                <input type="text" name="features" placeholder="Feature 1, Feature 2, Feature 3">
            </div>
            
            <div class="checkbox-group">
                <label><input type="checkbox" name="popular"> Popular Plan</label>
            </div>
            
            <button type="submit" class="btn" style="margin-top: 20px;">Create Plan</button>
        </form>
    </div>
</body>
</html>
'''

ADMIN_USERS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Users - BLACK ADMIN</title>
    <style>
        body {
            background: #0a0a0a;
            color: white;
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 40px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
        }
        .logo {
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(135deg, #ff00de, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .nav a {
            color: #00d4ff;
            text-decoration: none;
            margin-left: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(255,255,255,0.02);
            border-radius: 15px;
            overflow: hidden;
        }
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th {
            background: rgba(255,255,255,0.05);
            color: #00ffcc;
        }
        select {
            padding: 8px;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 5px;
            color: white;
        }
        .btn {
            background: linear-gradient(135deg, #00ffcc, #00d4ff);
            color: #000;
            padding: 8px 15px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">👥 USER MANAGEMENT</div>
        <div class="nav">
            <a href="/admin/dashboard">Dashboard</a>
            <a href="/logout">Logout</a>
        </div>
    </div>

    <table>
        <tr>
            <th>Username</th>
            <th>Current Plan</th>
            <th>Status</th>
            <th>Change Plan</th>
        </tr>
        {% for username in users %}
        {% set user_sub = subs.get(username, {}) %}
        <tr>
            <td>{{ username }}</td>
            <td>{{ user_sub.get('plan', 'starter')|upper }}</td>
            <td>{% if user_sub.get('active') %}Active{% else %}Inactive{% endif %}</td>
            <td>
                <form method="post" action="/admin/user/{{ username }}/setplan" style="display: flex; gap: 10px;">
                    <select name="plan_id">
                        {% for plan_id, plan in plans.items() %}
                        <option value="{{ plan_id }}" {% if plan_id == user_sub.get('plan') %}selected{% endif %}>{{ plan.name }}</option>
                        {% endfor %}
                    </select>
                    <button type="submit" class="btn">Update</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
'''

ADMIN_PAYMENTS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Payments - BLACK ADMIN</title>
    <style>
        body {
            background: #0a0a0a;
            color: white;
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 40px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
        }
        .logo {
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(135deg, #ff00de, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .nav a {
            color: #00d4ff;
            text-decoration: none;
            margin-left: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(255,255,255,0.02);
            border-radius: 15px;
            overflow: hidden;
        }
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th {
            background: rgba(255,255,255,0.05);
            color: #00ffcc;
        }
        .status {
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .status.completed { background: rgba(0,255,204,0.2); color: #00ffcc; }
        .status.pending { background: rgba(255,165,0,0.2); color: orange; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">💰 PAYMENTS</div>
        <div class="nav">
            <a href="/admin/dashboard">Dashboard</a>
            <a href="/logout">Logout</a>
        </div>
    </div>

    <table>
        <tr>
            <th>Payment ID</th>
            <th>User</th>
            <th>Plan</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Date</th>
        </tr>
        {% for payment_id, payment in payments.items() %}
        <tr>
            <td>{{ payment_id[:8] }}...</td>
            <td>{{ payment.user }}</td>
            <td>{{ payment.plan|upper }}</td>
            <td>${{ payment.amount }}</td>
            <td><span class="status {{ payment.status }}">{{ payment.status|upper }}</span></td>
            <td>{{ payment.created_at[:10] }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
'''

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)