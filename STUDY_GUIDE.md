# URL Shortener - Complete Study Guide

> Read this fully before your demo. It covers how every part works, what to say, which file to open, and every question your teacher might ask.

---

## Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [Tech Stack - What Libraries We Used and Why](#2-tech-stack)
3. [Project Folder Structure](#3-project-folder-structure)
4. [How the System Works - Full Flow](#4-system-flow)
5. [File-by-File Explanation](#5-file-by-file-explanation)
6. [Database Models Explained](#6-database-models)
7. [Demo Script - Step by Step](#7-demo-script)
8. [Viva Questions and Answers](#8-viva-questions)

---

## 1. What This Project Does

This is a **URL Shortener** - similar to bit.ly or tinyurl.com.

**Core idea:** You give it a long URL like `https://www.example.com/very/long/path?with=params`, it generates a short link like `http://localhost:8000/aB3dEfG/`, and when someone visits that short link they get redirected to the original URL.

**Features:**

| Feature         | What it does                                                             |
| --------------- | ------------------------------------------------------------------------ |
| URL Shortening  | Takes a long URL, generates a 7-character short code using `nanoid`      |
| Custom Aliases  | User can set their own alias like `/my-project` instead of a random code |
| Expiry Dates    | Links can be set to expire after a certain date/time                     |
| Click Analytics | Every time someone clicks the link, it records IP, browser, referrer     |
| User Accounts   | Login/register so users can manage their own links                       |
| Dashboard       | Logged-in users see all their links with click counts                    |
| Django Admin    | Full admin panel at `/admin/` to manage everything                       |

---

## 2. Tech Stack

| Library             | Why we used it                                                               |
| ------------------- | ---------------------------------------------------------------------------- |
| **Django**          | Main Python web framework - handles routing, templates, forms, ORM           |
| **nanoid**          | Generates short unique IDs - used to create the 7-char short codes           |
| **django-ipware**   | Gets the real IP address of visitors, even behind proxies                    |
| **whitenoise**      | Serves static files (CSS, JS) directly from Django without a separate server |
| **gunicorn**        | Production WSGI server to run the Django app                                 |
| **psycopg2-binary** | PostgreSQL driver (used in production with Docker)                           |

**Why nanoid specifically?**

- It generates URL-safe random strings
- Very low chance of collision (same ID generated twice)
- Simple one-line usage: `generate(size=7)`
- Much cleaner than writing our own random string generator

---

## 3. Project Folder Structure

```
py-shorterner/
│
├── manage.py                  # Django's command-line tool (run server, migrations etc.)
├── requirements.txt           # All pip packages needed
├── db.sqlite3                 # SQLite database file (auto-created)
│
├── urlshortener/              # Django project settings folder
│   ├── settings.py            # All settings in one place
│   ├── urls.py                # Main URL routing - just includes shortener.urls
│   └── wsgi.py                # Entry point for web server
│
└── shortener/                 # Main app with all our logic
    ├── models.py              # Database tables (ShortenedURL, ClickEvent)
    ├── views.py               # Web page handlers (home, dashboard, redirect, etc.)
    ├── forms.py               # HTML form classes (for URL input, registration)
    ├── validators.py          # Input validation (URL format, alias format)
    ├── utils.py               # Helper functions (generate short code, get IP)
    ├── admin.py               # Configure Django admin panel
    ├── urls.py                # All URL patterns for the app
    ├── migrations/            # Database migration files (auto-generated)
    └── templates/             # HTML files live INSIDE the app folder
        ├── shortener/         # Namespace folder (same name as app)
        │   ├── base.html      # Base layout (navbar, messages)
        │   ├── home.html      # Home page with the URL input form
        │   ├── dashboard.html # User's list of links
        │   ├── link_form.html # Create / Edit link form
        │   ├── analytics.html # Click analytics for a single link
        │   └── confirm_delete.html  # Delete confirmation
        └── registration/      # Django auth templates (must be named this)
            ├── login.html     # Login page
            └── register.html  # Registration page
```

---

## 4. System Flow

### 4.1 Shortening a URL (the main feature)

```
User types URL into form on homepage
         |
         v
home() view in views.py handles POST request
         |
         v
ShortenURLForm validates the input:
  - Is the URL valid? (must start with http:// or https://)
  - Is the custom alias already taken?
         |
         v
generate_unique_short_code() in utils.py:
  - calls nanoid's generate(size=7)
  - checks if that code already exists in database
  - loops until a unique code is found
         |
         v
ShortenedURL object saved to database
         |
         v
Short URL displayed to user: http://localhost:8000/aB3dEfG/
```

### 4.2 Redirecting (when someone clicks the short link)

```
User visits http://localhost:8000/aB3dEfG/
         |
         v
Django routes to redirect_url() in views.py
         |
         v
Look up 'aB3dEfG' in database:
  - First check custom_alias column
  - Then check short_code column
         |
         v
Checks:
  - Is the link active? (is_active = True)
  - Has it expired? (expires_at < now)
         |
         v
Increment click_count by 1
         |
         v
Save a ClickEvent record:
  - IP address of visitor
  - Browser (user agent)
  - Where they came from (referrer)
         |
         v
HTTP 302 Redirect to original_url
```

### 4.3 User Registration and Login Flow

```
User fills register form
         |
         v
RegisterForm validates username, email, password
         |
         v
User object created in Django's built-in auth system
         |
         v
User automatically logged in
         |
         v
Redirected to /dashboard/
```

---

## 5. File-by-File Explanation

### `shortener/utils.py`

```python
from nanoid import generate
from ipware import get_client_ip as ipware_get_client_ip

def generate_unique_short_code():
    from shortener.models import ShortenedURL
    while True:
        code = generate(size=7)  # generates something like "aB3dEfG"
        if not ShortenedURL.objects.filter(short_code=code).exists():
            return code  # only return if it doesn't already exist in DB

def get_client_ip(request):
    ip, _ = ipware_get_client_ip(request)
    return ip or ''
```

`nanoid` generates the short code. `django-ipware` handles getting the visitor's IP - it automatically checks `X-Forwarded-For` and other headers so it works correctly even behind proxies and load balancers. Much cleaner than doing it manually.

---

### `shortener/models.py`

Two database tables:

**ShortenedURL** - the main table

- Stores the original URL, short code, custom alias, expiry date, click count
- `effective_code` property: returns custom_alias if set, otherwise short_code
- `is_expired` property: checks if current time is past expires_at
- `increment_click()`: adds 1 to click_count and saves

**ClickEvent** - analytics table

- Every click gets one row here
- Stores IP address, browser, referrer
- Linked to ShortenedURL with a ForeignKey

---

### `shortener/views.py`

All the web page logic:

**`home(request)`** - The homepage. Shows the form. On POST, validates, generates short code, saves, shows result.

**`dashboard(request)`** - Requires login. Shows all URLs created by the logged-in user.

**`create_link(request)`** - Requires login. Separate form to create a new link (similar to home but always saves to user).

**`edit_link(request, pk)`** - Requires login. Loads existing link by ID (pk), lets user edit original_url, alias, expiry.

**`delete_link(request, pk)`** - Requires login. Shows confirmation page. On POST confirmation, deletes the link.

**`analytics(request, pk)`** - Requires login. Shows click history for a specific link.

**`redirect_url(request, short_code)`** - The redirect handler. Looks up the code, checks if valid, tracks the click, redirects.

**`register(request)`** - Registration page. Uses Django's built-in UserCreationForm extended with email field.

---

### `shortener/validators.py`

Two validation functions:

**`validate_url(url)`** - Uses Django's built-in `URLValidator` to check if URL is valid. Only http:// and https:// are allowed.

**`validate_custom_alias(alias)`** - Checks: 3-50 characters, only letters/numbers/hyphens allowed.

---

### `shortener/forms.py`

**`RegisterForm`** - Extends Django's `UserCreationForm` to add a required email field.

**`ShortenURLForm`** - A ModelForm based on `ShortenedURL`. Has Bootstrap-styled widgets. Custom `clean_` methods call our validators and also check for duplicate aliases.

---

### `urlshortener/settings.py`

All Django configuration in one file:

- `INSTALLED_APPS` - lists all Django apps including our `shortener` app
- `DATABASES` - uses SQLite locally, switches to PostgreSQL when `POSTGRES_HOST` env var is set (Docker)
- `LOGIN_REDIRECT_URL = '/dashboard/'` - where to go after login
- `STATICFILES_STORAGE` - whitenoise handles static files

---

### `urlshortener/urls.py`

The main entry point for Django's URL resolver. Kept minimal - just wires admin and includes all app routes:

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('shortener.urls')),
]
```

All the actual URL patterns live in `shortener/urls.py`.

---

### `shortener/urls.py`

All URL patterns for the whole project in one place:

```
/                   -> home view
/dashboard/         -> dashboard view (login required)
/create/            -> create_link view
/edit/<pk>/         -> edit_link view
/delete/<pk>/       -> delete_link view
/analytics/<pk>/    -> analytics view
/accounts/login/    -> Django's built-in LoginView
/accounts/logout/   -> Django's built-in LogoutView
/accounts/register/ -> our register view
/<short_code>/      -> redirect_url view (must be last!)
```

The short_code route is last because `<str:short_code>` would match anything - if it was first it would catch all routes.

---

## 6. Database Models

### Visual Relationship

```
      User (Django built-in)
       |
       `-- ShortenedURL (user can be null for anonymous)
             |
             `-- ClickEvent (one URL has many click events)
```

### ShortenedURL columns

| Column       | Type            | Description                            |
| ------------ | --------------- | -------------------------------------- |
| id           | Integer         | Auto-increment primary key             |
| user         | ForeignKey      | Which user created it (nullable)       |
| original_url | URLField        | The long URL                           |
| short_code   | CharField       | The generated nanoid code (unique)     |
| custom_alias | CharField       | Optional user-defined alias (unique)   |
| created_at   | DateTimeField   | When it was created                    |
| expires_at   | DateTimeField   | Optional expiry time                   |
| click_count  | PositiveInteger | How many times it was clicked          |
| is_active    | Boolean         | Can be toggled off to disable the link |

---

## 7. Demo Script

> Follow these steps during your demo. Open files in the order shown.

---

### Step 1 - Start the Project

Tell the teacher: _"This is a URL Shortener built with Django and Python. Let me show you how to run it first."_

Open terminal and run:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open browser at `http://localhost:8000/`

---

### Step 2 - Show the Home Page

Open file: **`shortener/templates/shortener/home.html`**

Say: _"This is the home page. Any user, even without logging in, can shorten a URL. The form is handled by the `ShortenURLForm` class."_

**Demo:** Type `https://www.google.com/search?q=python+django+tutorial` and click Shorten.

Show the short URL that appears. Copy it.

---

### Step 3 - Show URL Redirection

Open file: **`shortener/views.py`** - scroll to `redirect_url` function

Say: _"When someone visits the short link, Django routes it to the `redirect_url` function. It looks up the code in the database, records the click event, and does an HTTP redirect to the original URL."_

**Demo:** Paste the short URL in the browser and show that it redirects to Google.

---

### Step 4 - Show How Short Code is Generated

Open file: **`shortener/utils.py`**

Say: _"To generate the short code, I used a library called `nanoid`. It generates a 7-character random string using letters and numbers. I then check the database to make sure no other URL has the same code - this prevents collisions."_

---

### Step 5 - Show the Database Model

Open file: **`shortener/models.py`**

Say: _"Here is the main database model - `ShortenedURL`. Each row in this table represents one shortened URL. It stores the original URL, the short code, an optional custom alias, click count, and expiry date."_

Point to `increment_click()`: _"Each time someone clicks the link, this method adds 1 to the click count and saves it."_

Point to `is_expired` property: _"This property checks if the current time is past the expiry date."_

---

### Step 6 - Show User Registration and Login

Open file: **`shortener/forms.py`** - show `RegisterForm`

Say: _"For user registration, I extended Django's built-in `UserCreationForm` and added an email field. Django handles all the password hashing and security automatically."_

**Demo:** Go to `http://localhost:8000/accounts/register/` and register a new account.

---

### Step 7 - Show Dashboard

Open file: **`shortener/views.py`** - scroll to `dashboard` function

Say: _"After login, the user is taken to the dashboard. The `@login_required` decorator makes sure only logged-in users can access it. It fetches only that user's links from the database."_

Open file: **`shortener/templates/shortener/dashboard.html`**

Say: _"The template loops over each link and shows the short code, original URL, click count, and action buttons."_

**Demo:** Create a new link from the dashboard, edit it, view analytics.

---

### Step 8 - Show Click Analytics

Open file: **`shortener/templates/shortener/analytics.html`**

Say: _"For each link, the user can see analytics - how many times it was clicked, when, from what IP address, what browser, and from which website."_

Open file: **`shortener/models.py`** - show `ClickEvent` class

Say: _"The `ClickEvent` model stores one record for each click. It is linked to `ShortenedURL` through a ForeignKey relationship."_

---

### Step 9 - Show Admin Panel

Go to `http://localhost:8000/admin/`

First create a superuser if not done:

```bash
python manage.py createsuperuser
```

Say: _"Django provides a built-in admin panel. I registered all our models there. The admin can view all URLs and all click events."_

Open file: **`shortener/admin.py`**

Say: _"These few lines of code are enough to get a full admin interface for each model."_

---

### Step 10 - Show Project Settings

Open file: **`urlshortener/settings.py`**

Say: _"All Django settings are in one file. I am using SQLite as the database which is a simple file-based database - no separate database server needed for development. For production with Docker, we can switch to PostgreSQL."_

---

## 8. Viva Questions

### Basic Questions

**Q: What is a URL shortener?**
A: A URL shortener converts a long URL into a much shorter one. When someone visits the short URL, they are automatically redirected to the original long URL. It is useful for sharing links, tracking clicks, and making URLs more readable.

**Q: Which programming language and framework did you use?**
A: I used Python as the programming language and Django as the web framework. Django follows the MVT (Model-View-Template) architectural pattern.

**Q: What is Django?**
A: Django is a high-level Python web framework that encourages rapid development and clean design. It comes with many built-in features like an ORM, authentication system, admin panel, form handling, and CSRF protection.

**Q: What is nanoid and why did you use it?**
A: nanoid is a small, URL-safe, unique string ID generator library. I used it to generate the 7-character short codes for the URLs. It uses a random combination of letters and numbers, which makes it very unlikely for two codes to be the same. It is simpler and cleaner than writing a random string generator from scratch.

**Q: What database did you use?**
A: I used SQLite for development. SQLite is a file-based database that comes built into Python - no separate server is needed. In production (with Docker), I configured PostgreSQL for better performance and multi-user support.

**Q: What is an ORM?**
A: ORM stands for Object-Relational Mapper. It lets us work with the database using Python classes and objects instead of writing raw SQL queries. In Django, each model class represents a database table, and we can do operations like `ShortenedURL.objects.filter(user=request.user)` instead of writing `SELECT * FROM shortener_shortenedurl WHERE user_id = ...`.

---

### Django-Specific Questions

**Q: What is the MVT pattern in Django?**
A: MVT stands for Model-View-Template.

- **Model** - defines the database structure (our `models.py`)
- **View** - contains the business logic, handles requests and responses (our `views.py`)
- **Template** - the HTML files that render the user interface (our `templates/` folder)

**Q: What is a migration?**
A: A migration is how Django tracks changes to your database schema. When you create or modify a model, you run `python manage.py makemigrations` to create a migration file, then `python manage.py migrate` to apply it to the database. This way the database stays in sync with your models.

**Q: What is `@login_required`?**
A: It is a decorator provided by Django's authentication system. When you put `@login_required` above a view function, Django automatically checks if the user is logged in. If not, it redirects them to the login page. I used it on `dashboard`, `create_link`, `edit_link`, `delete_link`, and `analytics` views.

**Q: What is a ForeignKey?**
A: A ForeignKey is a database relationship. It links one table to another. For example, `ClickEvent` has a ForeignKey to `ShortenedURL`. This means each click event belongs to one shortened URL. One shortened URL can have many click events (one-to-many relationship).

**Q: What is `get_object_or_404`?**
A: It is a Django shortcut that tries to get an object from the database. If the object does not exist, it automatically returns an HTTP 404 Not Found response instead of raising an unhandled exception. I use it to fetch links by primary key in the edit, delete, and analytics views.

**Q: What is CSRF protection?**
A: CSRF stands for Cross-Site Request Forgery. It is a type of attack where a malicious website tricks a user's browser into making a request to another website where the user is logged in. Django includes CSRF protection by default - it adds a hidden token to every form, and verifies that token on POST requests.

**Q: What is the difference between `GET` and `POST` in HTTP?**
A: `GET` is used to retrieve data (like loading a page). `POST` is used to send data to the server (like submitting a form). In our views, GET shows the form and POST processes the form submission. We check `if request.method == 'POST':` to handle form submissions.

**Q: What does `commit=False` mean in `form.save(commit=False)`?**
A: Normally `form.save()` creates the object and saves it to the database immediately. `commit=False` creates the Python object but does NOT save it to the database yet. This lets us add additional fields (like `obj.user = request.user` and `obj.short_code = generate_unique_short_code()`) before saving.

**Q: What is `request.build_absolute_uri()`?**
A: It builds a complete URL including the protocol and domain. For example, if your site is `http://localhost:8000`, then `request.build_absolute_uri('/')` returns `http://localhost:8000/`. I use it to build the full short URL to display to the user.

**Q: How does Django's admin work?**
A: Django comes with a built-in admin interface. You register your models in `admin.py` using `@admin.register(ModelName)` and immediately get a full CRUD interface at `/admin/`. You can customize what columns to show in the list, what fields to filter by, and what to search on.

**Q: What is a `ModelForm`?**
A: A `ModelForm` is a form that is automatically generated from a database model. Instead of defining each form field manually, you specify the model and which fields to include. Django figures out the field types automatically. `ShortenURLForm` is a ModelForm based on the `ShortenedURL` model.

**Q: What is the `Meta` class inside a model or form?**
A: `Meta` is an inner class used to provide metadata about the model or form. In a model, it can set the default ordering (`ordering = ['-created_at']`). In a form, it specifies which model to use and which fields to include.

---

### Feature-Specific Questions

**Q: How does the URL redirect work?**
A: When someone visits `/aB3dEfG/`, Django routes the request to `redirect_url(request, short_code)`. The function looks up the short code in the database (checking both `short_code` and `custom_alias` columns). If found and active and not expired, it records a `ClickEvent`, increments the click count, and returns an HTTP redirect to the original URL using Django's `redirect()` function.

**Q: What is a custom alias?**
A: Instead of getting a random code like `aB3dEfG`, the user can choose their own alias like `my-project`. The custom alias is validated to be 3-50 characters, contain only letters/numbers/hyphens, and be unique. When looking up a short code, we check the `custom_alias` column first, then the `short_code` column.

**Q: How do you prevent the same short code from being generated twice?**
A: In `utils.py`, the `generate_unique_short_code()` function uses a while loop. It generates a code with nanoid, then queries the database to check if that code already exists. If it does, it generates a new one. It keeps looping until a unique code is found. In practice, with 7 characters and 62 possible characters per position, there are 62^7 = 3.5 trillion possible codes, so collisions are extremely rare.

**Q: How does the expiry feature work?**
A: The `ShortenedURL` model has an `expires_at` DateTimeField that is optional (nullable). The `is_expired` property compares the current time (`timezone.now()`) with `expires_at`. In the `redirect_url` view, if the link is expired, we raise an `Http404` error. The form validation ensures the user cannot set an expiry date in the past.

**Q: How is click tracking implemented?**
A: When a redirect happens, two things occur:

1. `obj.increment_click()` is called, which adds 1 to `click_count` and saves the model.
2. A `ClickEvent` object is created with the visitor's IP address (from `get_client_ip()`), their browser's user-agent, and the referrer URL.

**Q: How do you get the visitor's IP address?**
A: In `utils.py`, I use the `django-ipware` library. It provides a `get_client_ip(request)` function that handles all the complexity - it checks `X-Forwarded-For`, `X-Real-IP`, and other headers automatically. This works correctly even when the app is behind a proxy or load balancer, without needing to write that logic manually.

---

### Architecture and Design Questions

**Q: Why is the `/<short_code>/` route last in urls.py?**
A: Because `<str:short_code>` matches any string. If it was placed first, it would intercept every other URL - `/dashboard/` would be caught as a short code "dashboard", `/admin/` would be caught as "admin", etc. By placing it last, all the specific routes are matched first, and only unmatched paths fall through to the short code lookup.

**Q: What is WhiteNoise and why is it needed?**
A: WhiteNoise is a library that allows Django to serve static files (CSS, JavaScript, images) directly. Normally in production you would use a separate web server like Nginx to serve static files. WhiteNoise simplifies deployment by letting Django handle this itself, while still being efficient.

**Q: How does user isolation work - how do you make sure a user can only see their own links?**
A: In the dashboard and other views, the database query always includes `filter(user=request.user)`. So even if you know the primary key of another user's link, the `get_object_or_404(ShortenedURL, pk=pk, user=request.user)` query will fail (return 404) because both conditions must match - right primary key AND belonging to the logged-in user.

**Q: What happens if someone tries to access a short URL that doesn't exist?**
A: In `redirect_url`, if we cannot find the short code in either `custom_alias` or `short_code` columns, we call `raise Http404("Short URL not found.")`. Django catches this and returns a 404 page to the user.

**Q: What is `update_fields` in `save(update_fields=['click_count'])`?**
A: When you call `obj.save()` normally, Django updates ALL columns in the database row. `update_fields` tells Django to only update those specific columns. This is more efficient - especially useful for `increment_click()` which is called on every redirect, because it only updates the click_count column instead of rewriting the entire row.

**Q: What is the difference between `null=True` and `blank=True` in model fields?**
A: `null=True` means the database column can store a NULL value. `blank=True` means the form field is optional (can be left empty). You usually need both when making a field optional in a form that saves to the database. For CharField specifically, Django convention is to use `blank=True` without `null=True` (store empty string instead of NULL), but for DateTimeField and ForeignKey, you need `null=True` as well.

---

### Docker Questions (if teacher asks)

**Q: Why did you use Docker?**
A: Docker lets us package the application with everything it needs - Python, all libraries, and the configuration - into a container. This means the app will run the same way on any computer, solving the "it works on my machine" problem. The `docker-compose.yml` also spins up a PostgreSQL database alongside the app.

**Q: What is docker-compose?**
A: docker-compose is a tool for running multiple containers together. Our `docker-compose.yml` defines two services - `web` (the Django app) and `db` (PostgreSQL). With one command (`docker-compose up`), both start together and the app automatically connects to the database.

---

### Questions You Might Be Asked to Explain Code

**Q: Explain this line: `obj = ShortenedURL.objects.filter(custom_alias=short_code, is_active=True).first()`**
A: This queries the database table for `ShortenedURL` where the `custom_alias` column equals the short_code from the URL AND `is_active` is True. `.first()` returns the first result or `None` if nothing is found. We use this to check if the short code is a custom alias first.

**Q: Explain `form.save(commit=False)`**
A: This creates a `ShortenedURL` Python object from the form data but does NOT yet write it to the database. We then set `obj.user = request.user` and `obj.short_code = generate_unique_short_code()` on the object before calling `obj.save()` to actually write to the database.

**Q: Why do you check `if request.user.is_authenticated:` in the home view?**
A: The home page is accessible to everyone, including users who are not logged in. If the user IS logged in, we associate the link with their account so it appears in their dashboard. If they are not logged in, `obj.user` stays as None (because the user field is nullable) and the link is created anonymously.

**Q: What does `ordering = ['-created_at']` mean in the model Meta class?**
A: This sets the default ordering for database queries. The `-` prefix means descending order. So `ShortenedURL.objects.all()` will automatically return results sorted from newest to oldest. The `created_at` field stores when each link was created.

---

_Good luck with your demonstration! You have built a complete, working web application with user authentication, database storage, URL shortening with nanoid, and click analytics. Be confident - this is solid work._
