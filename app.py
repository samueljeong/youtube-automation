from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    return "서버 잘 뜸!"

@app.route("/sermon")
def sermon():
    return "설교 페이지 자리!"

if __name__ == "__main__":
    app.run(debug=True)