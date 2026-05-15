import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from pyairtable import Api

load_dotenv()

app = Flask(__name__, static_folder=str(Path(__file__).parent.parent / 'frontend'), static_url_path='')
CORS(app)

TOKEN = os.getenv('AIRTABLE_API_TOKEN')
BASE_ID = os.getenv('AIRTABLE_BASE_ID')
TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME', 'Table 1')

api = Api(TOKEN)
table = api.table(BASE_ID, TABLE_NAME)

FIELD_MAP = {
    'name': 'Course Name',
    'category': 'Catgoery',
    'platform': 'Plarform',
    'free': 'Free',
    'certificate': 'Certificate',
    'duration': 'Duration',
    'level': 'Level',
    'language': 'Language',
    'link': 'Course Link',
    'description': 'Description',
    'startDate': 'Start date',
}

def map_record(record):
    f = record.get('fields', {})
    thumbnails = f.get('Thumbnail', [])
    thumbnail_url = ''
    if thumbnails and isinstance(thumbnails, list):
        t = thumbnails[0]
        if isinstance(t, dict):
            thumbs = t.get('thumbnails', {})
            if thumbs and isinstance(thumbs, dict):
                large = thumbs.get('large', {})
                if large and isinstance(large, dict):
                    thumbnail_url = large.get('url', '') or ''
            if not thumbnail_url:
                thumbnail_url = t.get('url', '') or ''
    return {
        'id': record.get('id', ''),
        'name': f.get('Course Name', ''),
        'category': f.get('Catgoery', ''),
        'platform': f.get('Plarform', ''),
        'free': bool(f.get('Free', False)),
        'certificate': bool(f.get('Certificate', False)),
        'duration': f.get('Duration', ''),
        'level': f.get('Level', ''),
        'language': f.get('Language', ''),
        'link': f.get('Course Link', ''),
        'thumbnail': thumbnail_url,
        'description': f.get('Description', ''),
        'startDate': f.get('Start date', ''),
    }

def fetch_all():
    records = []
    for page in table.iterate():
        for record in page:
            records.append(map_record(record))
    return records

@app.route('/api/courses')
def get_courses():
    records = fetch_all()
    q = request.args.get('search', '').lower()
    language = request.args.get('language')
    category = request.args.get('category')
    platform = request.args.get('platform')
    level = request.args.get('level')
    free = request.args.get('free')
    certificate = request.args.get('certificate')

    if q:
        records = [c for c in records if q in c['name'].lower() or q in c['description'].lower()]
    if language:
        records = [c for c in records if c['language'] == language]
    if category:
        records = [c for c in records if c['category'] == category]
    if platform:
        records = [c for c in records if c['platform'] == platform]
    if level:
        records = [c for c in records if c['level'] == level]
    if free == 'true':
        records = [c for c in records if c['free']]
    if certificate == 'true':
        records = [c for c in records if c['certificate']]

    return jsonify(records)

@app.route('/api/filters')
def get_filters():
    records = fetch_all()
    return jsonify({
        'languages': sorted({c['language'] for c in records if c['language']}),
        'categories': sorted({c['category'] for c in records if c['category']}),
        'platforms': sorted({c['platform'] for c in records if c['platform']}),
        'levels': sorted({c['level'] for c in records if c['level']}),
    })

@app.route('/')
def index():
    return app.send_static_file('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 3000)), debug=True)
