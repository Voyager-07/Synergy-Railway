from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import json
import requests
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import render, redirect

from .forms import ProfileUpdateForm


# ---- Simple page views ----
def home(request):
    return render(request, "home.html")


def index(request):
    return render(request, "index.html")


def about(request):
    return render(request, "about.html")


@login_required
def profile(request):
    return render(request, "profile.html")


@login_required
def update_profile(request):
    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("/profile/")
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, "update_profile.html", {"form": form})


# ---- Helpers: formatting ----
def _fmt_date_no_leading_zeros(d: datetime) -> str:
    return f"{d.year}-{d.month}-{d.day}"


# ---- Codeforces helpers ----
def cf_contest_rating(cf_username: str) -> str:
    url = f"https://codeforces.com/api/user.rating?handle={cf_username}"
    resp = requests.get(url)
    if resp.status_code != 200 or resp.json().get("status") != "OK":
        return "<p>No rating data available for this user.</p>"

    results = resp.json()["result"]
    if not results:
        return "<p>No rating data available for this user.</p>"

    ratings = [r["newRating"] for r in results]
    contests = [r["contestName"] for r in results]
    width, height, padding = 330, 200, 40
    min_r, max_r = min(ratings), max(ratings)
    step = (width - 2 * padding) / max(1, (len(ratings) - 1))

    def y_for(r):
        return height - padding - ((r - min_r) / max(1, (max_r - min_r))) * (height - 2 * padding)

    points = [(padding + i * step, y_for(r)) for i, r in enumerate(ratings)]

    svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
    # grid + labels
    for i in range(6):
        value = min_r + i * (max_r - min_r) / 5
        y = height - padding - i * (height - 2 * padding) / 5
        svg.append(f'<line x1="{padding}" y1="{y}" x2="{width-padding}" y2="{y}" stroke="#3b3b3c" stroke-dasharray="4" />')
        svg.append(f'<text x="{padding-10}" y="{y+4}" text-anchor="end" font-size="12" fill="#4b5563">{round(value)}</text>')
    # lines
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="blue" stroke-width="2" />')
    svg.append("</svg>")
    return "\n".join(svg)


def cf_heatmap(cf_username: str):
    url = f"https://codeforces.com/api/user.status?handle={cf_username}"
    resp = requests.get(url)
    if resp.status_code != 200 or resp.json().get("status") != "OK":
        return []

    submission_counts = defaultdict(int)
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    for item in resp.json()["result"]:
        t = item.get("creationTimeSeconds")
        if t:
            date_key = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
            submission_counts[date_key] += 1

    start = one_year_ago
    end = datetime.now(timezone.utc)
    days = (end - start).days + 1
    return [{"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "intensity": submission_counts.get((start + timedelta(days=i)).strftime("%Y-%m-%d"), 0)} for i in range(days)]


def classify_submissions_cf(cf_username: str):
    url = f"https://codeforces.com/api/user.status?handle={cf_username}"
    resp = requests.get(url)
    if resp.status_code != 200 or resp.json().get("status") != "OK":
        return {"Easy": 0, "Medium": 0, "Hard": 0, "Total": 0}

    counts = {"Easy": 0, "Medium": 0, "Hard": 0}
    for s in resp.json()["result"]:
        if s.get("verdict") == "OK":
            rating = s["problem"].get("rating", 0)
            if rating <= 1200:
                counts["Easy"] += 1
            elif rating <= 1600:
                counts["Medium"] += 1
            else:
                counts["Hard"] += 1
    counts["Total"] = counts["Easy"] + counts["Medium"] + counts["Hard"]
    return counts


# ---- CodeChef helpers ----
def _fetch_codechef(cc_username: str) -> dict:
    url = f"https://codechef-api.vercel.app/handle/{cc_username}"
    resp = requests.get(url)
    return resp.json() if resp.status_code == 200 else {}


def cc_contest_rating_and_heatmap(cc_username: str):
    data = _fetch_codechef(cc_username)
    if not data:
        return ("", "", "", "", 0, "<p>No rating data available</p>", [])

    pname = data.get("name")
    pfp = data.get("profile")
    country_flag = data.get("countryFlag")
    title = data.get("stars")
    rank = data.get("globalRank")

    rating_data = [{"contest": e["name"], "rating": int(e["rating"])} for e in data.get("ratingData", [])]
    if not rating_data:
        chart = "<p>No rating data available for this user.</p>"
    else:
        ratings = [e["rating"] for e in rating_data]
        width, height, padding = 330, 200, 40
        min_r, max_r = min(ratings), max(ratings)
        step = (width - 2 * padding) / max(1, (len(ratings) - 1))
        def y_for(r): return height - padding - ((r - min_r) / max(1, (max_r - min_r))) * (height - 2 * padding)
        points = [(padding + i * step, y_for(r)) for i, r in enumerate(ratings)]

        parts = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        for i in range(6):
            value = min_r + i * (max_r - min_r) / 5
            y = height - padding - i * (height - 2 * padding) / 5
            parts.append(f'<line x1="{padding}" y1="{y}" x2="{width-padding}" y2="{y}" stroke="#3b3b3c" stroke-dasharray="4" />')
            parts.append(f'<text x="{padding-10}" y="{y+4}" text-anchor="end" font-size="12" fill="#4b5563">{round(value)}</text>')
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="blue" stroke-width="2" />')
        parts.append("</svg>")
        chart = "\n".join(parts)

    heatmap = []
    heatmap_data = data.get("heatMap", [])
    start = datetime(2024, 1, 1)
    for i in range(365):
        d = start + timedelta(days=i)
        key = _fmt_date_no_leading_zeros(d)
        intensity = next((item["value"] for item in heatmap_data if item["date"] == key), 0)
        heatmap.append({"date": key, "intensity": intensity})

    return pname, pfp, country_flag, title, rank, chart, heatmap


# ---- LeetCode helpers ----
def lc_contest_chart(username: str):
    url = "https://leetcode.com/graphql"
    query = """
    query userContestRankingInfo($username: String!) {
        userContestRankingHistory(username: $username) {
            attended
            rating
            contest {
                title
                startTime
            }
        }
    }"""
    try:
        resp = requests.post(url, json={"query": query, "variables": {"username": username}}, headers={"Content-Type": "application/json"})
        if resp.status_code != 200:
            return "<p>No contest data available for this user.</p>"
        history = resp.json().get("data", {}).get("userContestRankingHistory", [])
        user_contests = [{"contest": e["contest"]["title"], "rating": e["rating"]} for e in history if e.get("attended")]
        if not user_contests:
            return "<p>No contest data available for this user.</p>"

        ratings = [c["rating"] for c in user_contests]
        width, height, padding = 330, 200, 40
        min_r, max_r = min(ratings), max(ratings)
        step = (width - 2 * padding) / max(1, (len(ratings) - 1))
        def y_for(r): return height - padding - ((r - min_r) / max(1, (max_r - min_r))) * (height - 2 * padding)
        points = [(padding + i * step, y_for(r)) for i, r in enumerate(ratings)]

        parts = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        for i in range(6):
            value = min_r + i * (max_r - min_r) / 5
            y = height - padding - i * (height - 2 * padding) / 5
            parts.append(f'<line x1="{padding}" y1="{y}" x2="{width-padding}" y2="{y}" stroke="#3b3b3c" stroke-dasharray="4" />')
            parts.append(f'<text x="{padding-10}" y="{y+4}" text-anchor="end" font-size="12" fill="#4b5563">{round(value)}</text>')
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="blue" stroke-width="2" />')
        parts.append("</svg>")
        return "\n".join(parts)
    except requests.RequestException:
        return "<p>No contest data available for this user.</p>"


def lc_user_problems_solved(username: str):
    url = "https://leetcode.com/graphql"
    query = """
    query userProblemsSolved($username: String!) {
        allQuestionsCount { difficulty count }
        matchedUser(username: $username) {
            problemsSolvedBeatsStats { difficulty percentage }
            submitStatsGlobal { acSubmissionNum { difficulty count } }
        }
    }"""
    try:
        resp = requests.post(url, json={"query": query, "variables": {"username": username}}, headers={"Content-Type": "application/json"})
        if resp.status_code != 200:
            return {}
        data = resp.json().get("data", {})
        return {
            "allQuestionsCount": {item["difficulty"]: item["count"] for item in data.get("allQuestionsCount", [])},
            "problemsSolvedBeatsStats": {item["difficulty"]: item["percentage"] for item in data.get("matchedUser", {}).get("problemsSolvedBeatsStats", [])},
            "acSubmissionNum": {item["difficulty"]: item["count"] for item in data.get("matchedUser", {}).get("submitStatsGlobal", {}).get("acSubmissionNum", [])},
        }
    except requests.RequestException:
        return {}


def lc_profile(username: str):
    url = "https://leetcode.com/graphql"
    query = """
    query userPublicProfile($username: String!) {
        matchedUser(username: $username) {
            contestBadge { name expired hoverText icon }
            username
            profile { ranking userAvatar realName aboutMe school countryName }
        }
    }"""
    try:
        resp = requests.post(url, json={"query": query, "variables": {"username": username}}, headers={"Content-Type": "application/json"})
        if resp.status_code != 200:
            return {}
        data = resp.json().get("data", {}).get("matchedUser", {}) or {}
        return {
            "contestBadge": data.get("contestBadge", {}),
            "username": data.get("username", ""),
            "ranking": data.get("profile", {}).get("ranking", 0),
            "userAvatar": data.get("profile", {}).get("userAvatar", ""),
            "realName": data.get("profile", {}).get("realName", ""),
            "aboutMe": data.get("profile", {}).get("aboutMe", ""),
            "school": data.get("profile", {}).get("school"),
            "countryName": data.get("profile", {}).get("countryName", ""),
        }
    except requests.RequestException:
        return {}


def lc_heatmap(username: str, year: int = 2024):
    url = "https://leetcode.com/graphql"
    query = """
    query userProfileCalendar($username: String!, $year: Int) {
        matchedUser(username: $username) { userCalendar(year: $year) { submissionCalendar } }
    }"""
    try:
        resp = requests.post(url, json={"query": query, "variables": {"username": username, "year": year}}, headers={"Content-Type": "application/json"})
        if resp.status_code != 200:
            return []
        calendar = resp.json().get("data", {}).get("matchedUser", {}).get("userCalendar", {})
        submission_calendar = json.loads(calendar.get("submissionCalendar", "{}"))
        start = datetime(year, 1, 1)
        grid = []
        for i in range(365):
            d = start + timedelta(days=i)
            date_key = d.strftime("%Y-%m-%d")
            grid.append({"date": date_key, "value": submission_calendar.get(str(int(d.replace(tzinfo=timezone.utc).timestamp())), 0)})
        return grid
    except requests.RequestException:
        return []


# ---- Aggregator (concurrent + cached) ----
def aggregator(request):
    cc_username = getattr(request.user, "cc_username", None)
    cf_username = getattr(request.user, "cf_username", None)
    lc_username = getattr(request.user, "lc_username", None)
    cache_timeout = 300

    def get_or_cache(key, func, *args):
        if (val := cache.get(key)) is None:
            val = func(*args)
            cache.set(key, val, cache_timeout)
        return val

    futures = {}
    with ThreadPoolExecutor() as ex:
        if lc_username:
            futures["lc_data"] = ex.submit(get_or_cache, f"lc_data_{lc_username}", lc_profile, lc_username)
            futures["lc_chart"] = ex.submit(get_or_cache, f"lc_chart_{lc_username}", lc_contest_chart, lc_username)
            futures["lc_sub_data"] = ex.submit(get_or_cache, f"lc_sub_data_{lc_username}", lc_user_problems_solved, lc_username)
            futures["lc_heatmap"] = ex.submit(get_or_cache, f"lc_heatmap_{lc_username}", lc_heatmap, lc_username)
        if cc_username:
            futures["cc_data"] = ex.submit(get_or_cache, f"cc_data_{cc_username}", cc_contest_rating_and_heatmap, cc_username)
        if cf_username:
            futures["cf_ac_data"] = ex.submit(get_or_cache, f"cf_ac_data_{cf_username}", classify_submissions_cf, cf_username)
            futures["cf_chart"] = ex.submit(get_or_cache, f"cf_chart_{cf_username}", cf_contest_rating, cf_username)
            futures["cf_heatmap"] = ex.submit(get_or_cache, f"cf_heatmap_{cf_username}", cf_heatmap, cf_username)

    context = {}
    if lc_username:
        lc_data = futures["lc_data"].result()
        lc_chart = futures["lc_chart"].result()
        lc_sub_data = futures["lc_sub_data"].result()
        context.update({
            "lc_data": lc_data,
            "lc_contest_chart": lc_chart,
            "lc_sub_data": lc_sub_data,
            "lc_percent_solved": (float(lc_sub_data.get("acSubmissionNum", {}).get("All", 0)) / max(1, lc_sub_data.get("allQuestionsCount", {}).get("All", 1))) * 100,
            "lc_heatmap": futures["lc_heatmap"].result(),
        })

    if cc_username:
        name, pfp, flag, title, rank, cc_chart, cc_heatmap = futures["cc_data"].result()
        context.update({
            "name": name, "pfp": pfp, "flag": flag,
            "cc_username": cc_username, "cc_title": title, "cc_global_rank": rank,
            "cc_contest_chart": cc_chart, "cc_heatmap": cc_heatmap
        })

    if cf_username:
        cf_ac_data = futures["cf_ac_data"].result()
        context.update({
            "cf_sub_data": cf_ac_data,
            "cf_percent_solved": int((cf_ac_data.get("Total", 0) / 6000) * 100),
            "cf_contest_chart": futures["cf_chart"].result(),
            "cf_heatmap": futures["cf_heatmap"].result(),
        })

    return render(request, "aggregator.html", context)


# from django.shortcuts import render, redirect
# from django.contrib.auth.decorators import login_required
# from .forms import ProfileUpdateForm


# def home(request):
#     return render(request, 'index.html')

# @login_required
# def update_profile(request):
#     if request.method == 'POST':
#         form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
#         if form.is_valid():
#             form.save()
#             return redirect('/profile/')
#     else:
#         form = ProfileUpdateForm(instance=request.user)

#     return render(request, 'update_profile.html', {'form': form})

# @login_required
# def index(request):
#     return render(request, 'index.html')

# def about(request):
#     return render(request, 'about.html')


# @login_required
# def profile(request):
#     return render(request, 'profile.html')









# from collections import defaultdict
# from datetime import datetime, timedelta, timezone

# from django.shortcuts import render
# from django.http import HttpResponse
# from django.shortcuts import render
# import requests
# import json


# # Create your views here.

# def format_date_without_leading_zeros(date):
#     """
#     Format a date as 'YYYY-M-D' without leading zeros.
#     """
#     return f"{date.year}-{date.month}-{date.day}"


# def home(request):
#     return render(request, 'home.html', {})


# # CodeForces
# def cf_contest_rating(cf_username):
#     url = f'https://codeforces.com/api/user.rating?handle={cf_username}'

#     # Fetch data from the Codeforces API
#     response = requests.get(url)
#     if response.status_code == 200:
#         api_data = response.json()
#         if api_data['status'] == 'OK':
#             # Extract contest names and ratings from the API response
#             user_ratings = [
#                 {"contest": contest["contestName"], "rating": contest["newRating"]}
#                 for contest in api_data['result']
#             ]
#         else:
#             user_ratings = []  # Handle unexpected API response
#     else:
#         user_ratings = []  # Handle failed API request

#     # Handle case where no user ratings are available
#     if not user_ratings:
#         svg_content = "<p>No rating data available for this user.</p>"

#     # SVG dimensions and padding
#     width, height = 330, 200
#     padding = 40

#     # Extract ratings and calculate min and max
#     ratings = [entry["rating"] for entry in user_ratings]
#     max_rating, min_rating = max(ratings), min(ratings)

#     # Calculate step size for points
#     step = (width - 2 * padding) / (len(user_ratings) - 1)

#     # Calculate points
#     points = [
#         (
#             padding + i * step,  # x-coordinate
#             height - padding - ((rating - min_rating) / (max_rating - min_rating)) * (height - 2 * padding),
#             # y-coordinate
#         )
#         for i, rating in enumerate(ratings)
#     ]

#     # Generate SVG content
#     svg_content = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
#                 <!-- Background -->
#                 <rect width="100%" height="100%" fill="none"/>
#                 <!-- Grid lines and Y-axis labels -->
#             """
#     y_steps = 5
#     for i in range(y_steps + 1):
#         value = min_rating + (i * (max_rating - min_rating)) / y_steps
#         y = height - padding - (i * (height - 2 * padding)) / y_steps
#         svg_content += f"""
#                 <line x1="{padding}" y1="{y}" x2="{width - padding}" y2="{y}" stroke="#3b3b3c" stroke-dasharray="4" />
#                 <text x="{padding - 10}" y="{y + 4}" text-anchor="end" font-size="12" fill="#4b5563">{round(value)}</text>
#                 """

#     # Draw lines between points
#     for i in range(len(points) - 1):
#         x1, y1 = points[i]
#         x2, y2 = points[i + 1]
#         svg_content += f"""
#                 <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="blue" stroke-width="2" />
#                 """

#     # Close SVG
#     svg_content += "\n</svg>"
#     return svg_content


# def cf_heatmap(cf_username):
#     # Fetch data from Codeforces API
#     url = f"https://codeforces.com/api/user.status?handle={cf_username}"
#     response = requests.get(url)

#     if response.status_code != 200:
#         print("Failed to fetch data from the Codeforces API")
#         return []

#     data = response.json()
#     if data.get("status") != "OK":
#         print("Invalid response from the Codeforces API")
#         return []

#     # Collect submission dates and their counts
#     submission_dates = defaultdict(int)
#     one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)  # Define the start date (1 year back)
#     start_date_timestamp = int(one_year_ago.timestamp())  # Get the timestamp for filtering

#     for result in data["result"]:
#         creation_time = result["creationTimeSeconds"]

#         # Only include submissions from the past year
#         # if creation_time >= start_date_timestamp:
#         date_str = datetime.fromtimestamp(creation_time, tz=timezone.utc).strftime('%Y-%m-%d')
#         submission_dates[date_str] += 1

#     # Prepare the heatmap grid for the past year
#     start_date = one_year_ago
#     end_date = datetime.now(timezone.utc)
#     days_in_period = (end_date - start_date).days + 1
#     heatmap_grid = []

#     for i in range(days_in_period):
#         current_date = start_date + timedelta(days=i)
#         date_key = current_date.strftime('%Y-%m-%d')
#         intensity = submission_dates.get(date_key, 0)
#         heatmap_grid.append({
#             'date': date_key,
#             'intensity': intensity
#         })

#     return heatmap_grid


# def classify_submissions_cf(cf_username):
#     # API URL to fetch user submissions
#     url = f"https://codeforces.com/api/user.status?handle={cf_username}"

#     # Make the API request
#     response = requests.get(url)
#     if response.status_code != 200:
#         print(f"Failed to fetch data. HTTP Status Code: {response.status_code}")
#         return {}

#     data = response.json()
#     if data.get("status") != "OK":
#         print("Invalid response from Codeforces API")
#         return {}

#     # Initialize counters for classifications
#     classifications = {
#         "Easy": 0,
#         "Medium": 0,
#         "Hard": 0,
#         "Total": 0
#     }

#     # Process the API response
#     for submission in data["result"]:
#         if submission["verdict"] == "OK":  # Only process correct submissions
#             problem_rating = submission["problem"].get("rating", 0)  # Default rating is 0 if not provided

#             # Classify the submission based on the rating
#             if 0 <= problem_rating <= 1200:
#                 classifications["Easy"] += 1
#             elif 1201 <= problem_rating <= 1600:
#                 classifications["Medium"] += 1
#             elif 1601 <= problem_rating <= 4000:
#                 classifications["Hard"] += 1

#     # Calculate the total
#     classifications["Total"] = classifications["Easy"] + classifications["Medium"] + classifications["Hard"]

#     return classifications


# # CodeChef
# def fetch_codechef_data(cc_username):
#     """
#     Fetch data from the CodeChef API once and return the parsed JSON response.
#     """
#     url = f'https://codechef-api.vercel.app/handle/{cc_username}'
#     response = requests.get(url)

#     if response.status_code == 200:
#         return response.json()
#     else:
#         print("Failed to fetch data from the CodeChef API")
#         return {}


# def cc_contest_rating_and_heatmap(cc_username):
#     """
#     Generate contest rating chart (SVG) and heatmap data using a single API call.
#     """
#     # Fetch data once
#     api_data = fetch_codechef_data(cc_username)
#     pname = api_data['name']
#     pfp = api_data['profile']
#     country_flag = api_data['countryFlag']
#     title = api_data['stars']
#     rank = api_data['globalRank']

#     # Extract rating data
#     rating_data = api_data.get("ratingData", [])
#     if not rating_data:
#         contest_chart = "<p>No rating data available for this user.</p>"
#     else:
#         # Extract contest names and ratings
#         user_ratings = [
#             {"contest": entry["name"], "rating": int(entry["rating"])}
#             for entry in rating_data
#         ]

#         # SVG dimensions and padding
#         width, height = 330, 200
#         padding = 40

#         # Extract ratings and calculate min and max
#         ratings = [entry["rating"] for entry in user_ratings]
#         max_rating, min_rating = max(ratings), min(ratings)

#         # Calculate step size for points
#         step = (width - 2 * padding) / (len(user_ratings) - 1)

#         # Calculate points
#         points = [
#             (
#                 padding + i * step,  # x-coordinate
#                 height - padding - ((rating - min_rating) / (max_rating - min_rating)) * (height - 2 * padding),
#                 # y-coordinate
#             )
#             for i, rating in enumerate(ratings)
#         ]

#         # Generate SVG content
#         contest_chart = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
#                     <!-- Background -->
#                     <rect width="100%" height="100%" fill="none"/>
#                     <!-- Grid lines and Y-axis labels -->
#                 """
#         y_steps = 5
#         for i in range(y_steps + 1):
#             value = min_rating + (i * (max_rating - min_rating)) / y_steps
#             y = height - padding - (i * (height - 2 * padding)) / y_steps
#             contest_chart += f"""
#                     <line x1="{padding}" y1="{y}" x2="{width - padding}" y2="{y}" stroke="#3b3b3c" stroke-dasharray="4" />
#                     <text x="{padding - 10}" y="{y + 4}" text-anchor="end" font-size="12" fill="#4b5563">{round(value)}</text>
#                     """

#         # Draw lines between points
#         for i in range(len(points) - 1):
#             x1, y1 = points[i]
#             x2, y2 = points[i + 1]
#             contest_chart += f"""
#                     <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="blue" stroke-width="2" />
#                     """

#         # Close SVG
#         contest_chart += "\n</svg>"

#     # Extract heatmap data
#     heatmap_data = api_data.get("heatMap", [])
#     start_date = datetime(2024, 1, 1)
#     days_in_year = 365
#     heatmap_grid = []

#     for i in range(days_in_year):
#         current_date = start_date + timedelta(days=i)
#         date_key = format_date_without_leading_zeros(current_date)  # Custom formatting
#         intensity = next((item['value'] for item in heatmap_data if item['date'] == date_key), 0)
#         heatmap_grid.append({
#             'date': date_key,
#             'intensity': intensity
#         })

#     return pname, pfp, country_flag, title, rank, contest_chart, heatmap_grid


# def lc_contest_chart(username):
#     url = "https://leetcode.com/graphql"
#     svg_content = "<p>No contest data available for this user.</p>"

#     # GraphQL query
#     query = """
#     query userContestRankingInfo($username: String!) {
#         userContestRankingHistory(username: $username) {
#             attended
#             rating
#             contest {
#                 title
#                 startTime
#             }
#         }
#     }
#     """

#     # Variables for the query
#     variables = {"username": username}

#     # Fetch data from the API
#     try:
#         response = requests.post(
#             url,
#             json={"query": query, "variables": variables},
#             headers={"Content-Type": "application/json"}
#         )

#         if response.status_code == 200:
#             api_data = response.json()
#             history = api_data.get("data", {}).get("userContestRankingHistory", [])
#             user_contests = [
#                 {
#                     "contest": entry["contest"]["title"],
#                     "rating": entry["rating"]
#                 }
#                 for entry in history if entry.get("attended")
#             ]
#         else:
#             return svg_content
#     except requests.RequestException:
#         return svg_content

#     # Handle case where no user contests are available
#     if not user_contests:
#         return svg_content

#     # SVG dimensions and padding
#     width, height = 330, 200
#     padding = 40

#     # Extract ratings and calculate min and max
#     ratings = [entry["rating"] for entry in user_contests]
#     max_rating, min_rating = max(ratings), min(ratings)

#     # Calculate step size for points
#     step = (width - 2 * padding) / (len(user_contests) - 1)

#     # Calculate points
#     points = [
#         (
#             padding + i * step,  # x-coordinate
#             height - padding - ((rating - min_rating) / (max_rating - min_rating)) * (height - 2 * padding),
#             # y-coordinate
#         )
#         for i, rating in enumerate(ratings)
#     ]

#     # Generate SVG content
#     svg_content = f"""<svg width=\"{width}\" height=\"{height}\" xmlns=\"http://www.w3.org/2000/svg\">
#                 <!-- Background -->
#                 <rect width=\"100%\" height=\"100%\" fill=\"none\"/>
#                 <!-- Grid lines and Y-axis labels -->
#             """
#     y_steps = 5
#     for i in range(y_steps + 1):
#         value = min_rating + (i * (max_rating - min_rating)) / y_steps
#         y = height - padding - (i * (height - 2 * padding)) / y_steps
#         svg_content += f"""
#                 <line x1=\"{padding}\" y1=\"{y}\" x2=\"{width - padding}\" y2=\"{y}\" stroke=\"#3b3b3c\" stroke-dasharray=\"4\" />
#                 <text x=\"{padding - 10}\" y=\"{y + 4}\" text-anchor=\"end\" font-size=\"12\" fill=\"#4b5563\">{round(value)}</text>
#                 """

#     # Draw lines between points
#     for i in range(len(points) - 1):
#         x1, y1 = points[i]
#         x2, y2 = points[i + 1]
#         svg_content += f"""
#                 <line x1=\"{x1}\" y1=\"{y1}\" x2=\"{x2}\" y2=\"{y2}\" stroke=\"blue\" stroke-width=\"2\" />
#                 """

#     # Close SVG
#     svg_content += "\n</svg>"

#     return svg_content


# def lc_user_problems_solved(username):
#     # GraphQL endpoint
#     url = "https://leetcode.com/graphql"

#     # GraphQL query
#     query = """
#     query userProblemsSolved($username: String!) {
#         allQuestionsCount {
#             difficulty
#             count
#         }
#         matchedUser(username: $username) {
#             problemsSolvedBeatsStats {
#                 difficulty
#                 percentage
#             }
#             submitStatsGlobal {
#                 acSubmissionNum {
#                     difficulty
#                     count
#                 }
#             }
#         }
#     }
#     """

#     # Variables for the query
#     variables = {"username": username}

#     # Send the GraphQL request
#     try:
#         response = requests.post(
#             url,
#             json={"query": query, "variables": variables},
#             headers={"Content-Type": "application/json"}
#         )

#         if response.status_code == 200:
#             # Process the response JSON
#             data = response.json().get("data", {})

#             # Map structure
#             result_map = {
#                 "allQuestionsCount": {
#                     item["difficulty"]: item["count"]
#                     for item in data.get("allQuestionsCount", [])
#                 },
#                 "problemsSolvedBeatsStats": {
#                     item["difficulty"]: item["percentage"]
#                     for item in data.get("matchedUser", {}).get("problemsSolvedBeatsStats", [])
#                 },
#                 "acSubmissionNum": {
#                     item["difficulty"]: item["count"]
#                     for item in data.get("matchedUser", {}).get("submitStatsGlobal", {}).get("acSubmissionNum", [])
#                 }
#             }
#             # Dict Structure
#             # {
#             #     "allQuestionsCount": {
#             #         "All": 3399,
#             #         "Easy": 845,
#             #         "Medium": 1772,
#             #         "Hard": 782
#             #     },
#             #     "problemsSolvedBeatsStats": {
#             #         "Easy": 82.78,
#             #         "Medium": 88,
#             #         "Hard": 74.39
#             #     },
#             #     "acSubmissionNum": {
#             #         "All": 200,
#             #         "Easy": 64,
#             #         "Medium": 119,
#             #         "Hard": 17
#             #     }
#             # }
#             return result_map
#         else:
#             return {}
#     except requests.RequestException:
#         return {}


# def lc_profile(username):
#     # GraphQL endpoint
#     url = "https://leetcode.com/graphql"

#     # GraphQL query
#     query = """
#     query userPublicProfile($username: String!) {
#         matchedUser(username: $username) {
#             contestBadge {
#                 name
#                 expired
#                 hoverText
#                 icon
#             }
#             username
#             profile {
#                 ranking
#                 userAvatar
#                 realName
#                 aboutMe
#                 school
#                 countryName
#             }
#         }
#     }
#     """

#     # Variables for the query
#     variables = {"username": username}

#     # Initialize the map to be returned
#     result_map = {}

#     # Send the GraphQL request
#     try:
#         response = requests.post(
#             url,
#             json={"query": query, "variables": variables},
#             headers={"Content-Type": "application/json"}
#         )

#         if response.status_code == 200:
#             # Extract data from the response
#             data = response.json().get("data", {}).get("matchedUser", {})
#             if data:
#                 # Map variables
#                 result_map = {
#                     "contestBadge": data.get("contestBadge", {}),
#                     "username": data.get("username", ""),
#                     "ranking": data.get("profile", {}).get("ranking", 0),
#                     "userAvatar": data.get("profile", {}).get("userAvatar", ""),
#                     "realName": data.get("profile", {}).get("realName", ""),
#                     "aboutMe": data.get("profile", {}).get("aboutMe", ""),
#                     "school": data.get("profile", {}).get("school", None),
#                     "countryName": data.get("profile", {}).get("countryName", "")
#                 }
#         return result_map
#     except requests.RequestException:
#         return result_map


# def lc_heatmap(username):
#     # GraphQL query and endpoint
#     url = "https://leetcode.com/graphql"
#     query = """
#     query userProfileCalendar($username: String!, $year: Int) {
#         matchedUser(username: $username) {
#             userCalendar(year: $year) {
#                 submissionCalendar
#             }
#         }
#     }
#     """
#     variables = {
#         "username": username,
#         "year": 2024  # Update to the desired year
#     }

#     # Make a POST request to the GraphQL endpoint
#     response = requests.post(
#         url,
#         json={"query": query, "variables": variables},
#         headers={"Content-Type": "application/json"}
#     )

#     heatmap_data = []
#     if response.status_code == 200:
#         data = response.json()
#         calendar_data = data.get("data", {}).get("matchedUser", {}).get("userCalendar", {})
#         submission_calendar = json.loads(calendar_data.get("submissionCalendar", "{}"))

#         for timestamp, count in submission_calendar.items():
#             # Convert timestamp to a date in UTC
#             date = datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%d")
#             heatmap_data.append({"date": date, "value": count})
#     else:
#         print("Failed to fetch data from the API")
#         return []

#     # Prepare heatmap data for the year
#     start_date = datetime(2024, 1, 1)
#     days_in_year = 365
#     heatmap_grid = []

#     for i in range(days_in_year):
#         current_date = start_date + timedelta(days=i)
#         date_key = current_date.strftime("%Y-%m-%d")
#         # Debugging: Check if the date matches any in heatmap_data
#         intensity = next((item['value'] for item in heatmap_data if item['date'] == date_key), 0)

#         heatmap_grid.append({
#             'date': date_key,
#             'intensity': intensity
#         })

#     return heatmap_grid


# # def aggregator(request):
# #     cc_username = request.user.cc_username
# #     cf_username = request.user.cf_username
# #     lc_username = request.user.lc_username
# #
# #     lc_data = lc_profile(lc_username)
# #     lc_chart = lc_contest_chart(lc_username)
# #     lc_sub_data = lc_user_problems_solved(lc_username)
# #     lc_percent_solved = ((float(lc_sub_data['acSubmissionNum']['All'] / lc_sub_data['allQuestionsCount']['All'])) * 100)
# #
# #     name, pfp, flag, title, rank, cc_chart, cc_heatmap = cc_contest_rating_and_heatmap(cc_username)
# #
# #     cf_ac_data = classify_submissions_cf(cf_username)
# #     # print(cf_ac_data)
# #     cf_percent_solved = (int)((cf_ac_data["Total"] / 6000) * 100)
# #
# #     return render(request, 'profile.html', {
# #         'name': name,
# #         'pfp': pfp,
# #         'flag': flag,
# #         'cf_contest_chart': cf_contest_rating(cf_username),
# #         'cf_heatmap': cf_heatmap(cf_username),
# #         'cf_sub_data': cf_ac_data,
# #         'cf_percent_solved': cf_percent_solved,
# #
# #         'cc_username': cc_username,
# #         'cc_title': title,
# #         'cc_global_rank': rank,
# #         'cc_contest_chart': cc_chart,
# #         'cc_heatmap': cc_heatmap,
# #
# #         'lc_sub_data': lc_sub_data,
# #         'lc_percent_solved': lc_percent_solved,
# #         'lc_username': lc_username,
# #         'lc_data': lc_data,
# #         'lc_contest_chart': lc_chart,
# #         'lc_heatmap': lc_heatmap(lc_username),
# #     })













# from concurrent.futures import ThreadPoolExecutor
# from django.core.cache import cache
# from django.shortcuts import render


# # Aggregator V2.0

# # def aggregator(request):
# #     cc_username = request.user.cc_username
# #     cf_username = request.user.cf_username
# #     lc_username = request.user.lc_username
# #
# #     cache_timeout = 300  # Cache timeout in seconds (adjust as needed)
# #
# #     def get_or_cache(key, func, *args):
# #         if (data := cache.get(key)) is None:
# #             data = func(*args)
# #             cache.set(key, data, cache_timeout)
# #         return data
# #
# #     with ThreadPoolExecutor() as executor:
# #         future_lc_data = executor.submit(get_or_cache, f'lc_data_{lc_username}', lc_profile, lc_username)
# #         future_lc_chart = executor.submit(get_or_cache, f'lc_chart_{lc_username}', lc_contest_chart, lc_username)
# #         future_lc_sub_data = executor.submit(get_or_cache, f'lc_sub_data_{lc_username}', lc_user_problems_solved,
# #                                              lc_username)
# #         future_cc_data = executor.submit(get_or_cache, f'cc_data_{cc_username}', cc_contest_rating_and_heatmap,
# #                                          cc_username)
# #         future_cf_ac_data = executor.submit(get_or_cache, f'cf_ac_data_{cf_username}', classify_submissions_cf,
# #                                             cf_username)
# #         future_cf_chart = executor.submit(get_or_cache, f'cf_chart_{cf_username}', cf_contest_rating, cf_username)
# #         future_cf_heatmap = executor.submit(get_or_cache, f'cf_heatmap_{cf_username}', cf_heatmap, cf_username)
# #         future_lc_heatmap = executor.submit(get_or_cache, f'lc_heatmap_{lc_username}', lc_heatmap, lc_username)
# #
# #         lc_data = future_lc_data.result()
# #         lc_chart = future_lc_chart.result()
# #         lc_sub_data = future_lc_sub_data.result()
# #         lc_percent_solved = (float(lc_sub_data['acSubmissionNum']['All']) / lc_sub_data['allQuestionsCount'][
# #             'All']) * 100
# #
# #         name, pfp, flag, title, rank, cc_chart, cc_heatmap = future_cc_data.result()
# #
# #         cf_ac_data = future_cf_ac_data.result()
# #         cf_percent_solved = int((cf_ac_data["Total"] / 6000) * 100)
# #
# #         cf_contest_chart = future_cf_chart.result()
# #         cf_heatmap_data = future_cf_heatmap.result()
# #         lc_heatmap_data = future_lc_heatmap.result()
# #
# #     return render(request, 'aggregator.html', {
# #         'name': name,
# #         'pfp': pfp,
# #         'flag': flag,
# #         'cf_contest_chart': cf_contest_chart,
# #         'cf_heatmap': cf_heatmap_data,
# #         'cf_sub_data': cf_ac_data,
# #         'cf_percent_solved': cf_percent_solved,
# #
# #         'cc_username': cc_username,
# #         'cc_title': title,
# #         'cc_global_rank': rank,
# #         'cc_contest_chart': cc_chart,
# #         'cc_heatmap': cc_heatmap,
# #
# #         'lc_sub_data': lc_sub_data,
# #         'lc_percent_solved': lc_percent_solved,
# #         'lc_username': lc_username,
# #         'lc_data': lc_data,
# #         'lc_contest_chart': lc_chart,
# #         'lc_heatmap': lc_heatmap_data,
# #     })




# from concurrent.futures import ThreadPoolExecutor
# from django.core.cache import cache
# from django.shortcuts import render


# # Aggregator V2.1

# def aggregator(request):
#     cc_username = request.user.cc_username
#     cf_username = request.user.cf_username
#     lc_username = request.user.lc_username

#     cache_timeout = 300  # Cache timeout in seconds

#     def get_or_cache(key, func, *args):
#         if (data := cache.get(key)) is None:
#             data = func(*args)
#             cache.set(key, data, cache_timeout)
#         return data

#     futures = {}

#     with ThreadPoolExecutor() as executor:
#         if lc_username:
#             futures['lc_data'] = executor.submit(get_or_cache, f'lc_data_{lc_username}', lc_profile, lc_username)
#             futures['lc_chart'] = executor.submit(get_or_cache, f'lc_chart_{lc_username}', lc_contest_chart,
#                                                   lc_username)
#             futures['lc_sub_data'] = executor.submit(get_or_cache, f'lc_sub_data_{lc_username}',
#                                                      lc_user_problems_solved, lc_username)
#             futures['lc_heatmap'] = executor.submit(get_or_cache, f'lc_heatmap_{lc_username}', lc_heatmap, lc_username)

#         if cc_username:
#             futures['cc_data'] = executor.submit(get_or_cache, f'cc_data_{cc_username}', cc_contest_rating_and_heatmap,
#                                                  cc_username)

#         if cf_username:
#             futures['cf_ac_data'] = executor.submit(get_or_cache, f'cf_ac_data_{cf_username}', classify_submissions_cf,
#                                                     cf_username)
#             futures['cf_chart'] = executor.submit(get_or_cache, f'cf_chart_{cf_username}', cf_contest_rating,
#                                                   cf_username)
#             futures['cf_heatmap'] = executor.submit(get_or_cache, f'cf_heatmap_{cf_username}', cf_heatmap, cf_username)

#     context = {}

#     if lc_username:
#         context['lc_data'] = futures['lc_data'].result()
#         context['lc_contest_chart'] = futures['lc_chart'].result()
#         lc_sub_data = futures['lc_sub_data'].result()
#         context['lc_sub_data'] = lc_sub_data
#         context['lc_percent_solved'] = (float(lc_sub_data['acSubmissionNum']['All']) / lc_sub_data['allQuestionsCount'][
#             'All']) * 100
#         context['lc_heatmap'] = futures['lc_heatmap'].result()

#     if cc_username:
#         name, pfp, flag, title, rank, cc_chart, cc_heatmap = futures['cc_data'].result()
#         context.update({'name': name, 'pfp': pfp, 'flag': flag, 'cc_username': cc_username,
#                         'cc_title': title, 'cc_global_rank': rank, 'cc_contest_chart': cc_chart,
#                         'cc_heatmap': cc_heatmap})

#     if cf_username:
#         cf_ac_data = futures['cf_ac_data'].result()
#         context['cf_sub_data'] = cf_ac_data
#         context['cf_percent_solved'] = int((cf_ac_data["Total"] / 6000) * 100)
#         context['cf_contest_chart'] = futures['cf_chart'].result()
#         context['cf_heatmap'] = futures['cf_heatmap'].result()

#     return render(request, 'aggregator.html', context)

