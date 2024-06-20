from flask import Flask, render_template, jsonify, request
import pymongo
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from textblob import TextBlob
import re

app = Flask(__name__)

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["bookdatabase"]
collection = db["books"]

@app.route('/', methods=['GET'])
def index():
    book_names = get_book_names()
    return render_template('index.html', book_names=book_names)

@app.route('/all_books', methods=['GET'])
def all_books():
    # Fetch all authors with their books
    authors = collection.find({}, {"books": 1, "_id": 0})

    # Extract all books from each author
    books = [book for author in authors for book in author.get('books', [])]

    return jsonify(books)

@app.route('/book/<book_name>', methods=['GET'])
def book_details(book_name):
    # Adjusted to handle the nested structure (books within an author document)
    author_data = collection.find_one({"books.book_name": book_name}, {"_id": 0, "author_name": 1, "books.$": 1})
    if author_data and 'books' in author_data:
        book_data = author_data['books'][0]  # Extract the matched book
        reviews = book_data.get('reviews', [])
        pie_chart_url = generate_pie_chart(reviews)

        # Returning JSON data instead of rendering a template
        return jsonify({
            'title': book_data['book_name'],
            'author': author_data['author_name'],
            'summary': book_data.get('summary', 'No summary available'),
            'genres': book_data.get('genres', []),
            'pie_chart_url': pie_chart_url
        })
    else:
        return jsonify({"error": "Book not found"}), 404

@app.route('/search/<book_name>', methods=['GET'])
def search(book_name):
    # Create a case-insensitive regular expression for the book name
    regex_pattern = re.compile(book_name, re.IGNORECASE)

    # Adjusted to handle the nested structure (books within an author document)
    author_data = collection.find_one({"books.book_name": regex_pattern}, {"_id": 0, "author_name": 1, "books.$": 1})
    if author_data and 'books' in author_data:
        book_data = author_data['books'][0]  # Extract the matched book
        reviews = book_data.get('reviews', [])
        pie_chart_url = generate_pie_chart(reviews)

        # Returning JSON data instead of rendering a template
        return jsonify({
            'title': book_data['book_name'],
            'author': author_data['author_name'],
            'summary': book_data.get('summary', 'No summary available'),
            'genres': book_data.get('genres', []),
            'pie_chart_url': pie_chart_url
        })
    else:
        return jsonify({"error": "Book not found"}), 404
@app.route('/add_review/<book_name>', methods=['POST'])
def add_review(book_name):
    review_content = request.form.get('review')
    if not review_content:
        return jsonify({"error": "No review content provided"}), 400

    # Add the review to the database
    result = collection.update_one(
        {"books.book_name": book_name},
        {"$push": {"books.$.reviews": review_content}}
    )

    if result.modified_count:
        return jsonify({"success": "Review added"}), 200
    else:
        return jsonify({"error": "Failed to add review"}), 500
@app.route('/filter_genre/<genre>', methods=['GET'])
def filter_genre(genre):
    matching_books = []
    # Search for authors who have books with the specified genre
    authors = collection.find({"books.genres": genre}, {"_id": 0, "author_name": 1, "books": 1})
    
    for author in authors:
        for book in author['books']:
            if genre in book['genres']:
                book_data = {
                    "title": book['book_name'],
                    "summary": book['summary'],
                    "image_url": book['image_url']
                    # Add any other book details you want to display
                }
                matching_books.append(book_data)
    
    return jsonify({"books": matching_books})



def get_book_names():
    # Query to get distinct book names across all documents
    return collection.distinct("books.book_name")

def generate_pie_chart(reviews):
    positive_count, negative_count, neutral_count = 0, 0, 0

    for review in reviews:
        analysis = TextBlob(review)
        if analysis.sentiment.polarity > 0.45:
            positive_count += 1
        elif analysis.sentiment.polarity < 0:
            negative_count += 1
        else:
            neutral_count += 1

    # Create a pie chart
    labels = ['Positive', 'Negative', 'Neutral']
    sizes = [positive_count, negative_count, neutral_count]
    colors = ['lightgreen', 'lightcoral', 'lightskyblue']
    explode = (0.1, 0, 0)  # explode the first slice (Positive)

    plt.figure(figsize=(6, 6))
    plt.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', shadow=True, startangle=140)
    plt.axis('equal')  # Equal aspect ratio ensures the pie chart is circular.

    # Convert pie chart to a PNG image
    img = BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    pie_chart_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close()

    return pie_chart_url
if __name__ == '__main__':
    app.run(debug=True)
