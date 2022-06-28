from flask import Flask, render_template, request, url_for, flash, redirect, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import exc
# from sqlalchemy_imageattach.entity import Image, image_attachment

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length

from flask_bootstrap import Bootstrap

from flask_login import UserMixin, login_user, logout_user, LoginManager, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from datetime import date
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzzzz'
Bootstrap(app)

# file upload folder
app.config['UPLOAD_FOLDER'] = 'static/temp'
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1000 * 10
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

CATS = ['Merch', 'Household', 'SSS tier']


def is_allowed(filename):
    """we check that there is some filename (dot condition) and it's allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def calc_total(c: dict):
    """we suppose our cart c = {Product object id: [Product object, quantity, ....]}"""
    t_price, t_quantity = 0, 0
    for _ in c:
        t_price += c[_][0].p_price * c[_][1]
        t_quantity += c[_][1]
    return t_price, t_quantity


# login manager initialisation
login_manager = LoginManager()
login_manager.init_app(app)

##Connect to Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mystore.db'
# this has to be turned off to prevent flask-sqlalchemy framework from tracking events and save resources
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# I have to create this key to use CSRF protection for form
db = SQLAlchemy(app)


# bi-directional one-to-many relationship
class User(UserMixin, db.Model):
    # Usermixin contains some important methods for our User
    # base class to inherit when we create our db entities
    __tablename__ = "users"
    # has to be called as 'id' in order to accomplish login procedure
    id = db.Column(db.Integer, primary_key=True)
    u_date = db.Column(db.Date, default=date.today())

    # registration data
    user_name = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(20), nullable=False)
    private_details = db.Column(db.PickleType)
    # avatar = image_attachment('UserPicture')

    # each user has some purchased items (list of ids) and a single cart (last one)
    purchases = db.Column(db.PickleType)
    cart = db.Column(db.PickleType)

    # I just want to return a string with custom printable representation of an object, overrides standard one
    def __repr__(self):
        return f'<User_{self.id}: {self.user_name}>'


# class UserPicture(db.Model, Image):
#     """User picture model."""
#     __tablename__ = 'avatars'
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
#     user = relationship('User')


class Product(db.Model):
    __tablename__ = "products"
    p_id = db.Column(db.Integer, primary_key=True)
    p_category = db.Column(db.String(20), nullable=False)
    p_name = db.Column(db.String(50), unique=True, nullable=False)
    p_description = db.Column(db.String(200), nullable=False)
    p_price = db.Column(db.Integer, nullable=False)
    p_amount = db.Column(db.Integer, nullable=False)

    # p_image = image_attachment('ProductPicture')

    # I just want to return a string with custom printable representation of an object, overrides standard one
    def __repr__(self):
        return f'<Product_{self.p_id}: {self.p_name}>'


# class ProductPicture(db.Model, Image):
#     """User picture model."""
#     __tablename__ = 'productpics'
#     product_id = db.Column(db.Integer, db.ForeignKey('products.p_id'), primary_key=True)
#     product = relationship('Product')
#     # implement some kind of storage here


@app.before_first_request
def before_first_request():
    db.create_all()


# callback that returns User object by id
@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(int(user_id))


def admin_only(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return func(*args, **kwargs)

    return decorated


class LoginForm(FlaskForm):
    username_f = StringField(label='Username', validators=[DataRequired(), Length(min=1, max=30)])
    password_f = PasswordField(label='Password', validators=[DataRequired(), Length(min=1, max=30)])
    submit_f = SubmitField('Submit')


@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    # check if it's a valid POST request
    if form.validate_on_submit():
        r_user_name = request.form.get('username_f')
        r_user_password = request.form.get('password_f')
        try:
            result = db.session.query(User).filter_by(user_name=r_user_name).first()
            if check_password_hash(result.password, r_user_password):
                login_user(result)
                flash('You were successfully logged in')
                return redirect(url_for('index'))
            else:
                flash('Wrong password')
                return redirect(url_for('login'))
        except:
            flash('User with that e-mail not found.')
            return redirect(url_for('login'))
    else:
        return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    global cart
    current_user.cart = cart
    db.session.commit()
    cart = {}
    logout_user()
    return redirect(url_for('index'))


@app.route("/register", methods=['GET', 'POST'])
def register():
    form = LoginForm()
    if form.validate_on_submit():
        name = request.form.get('username_f')
        password = request.form.get('password_f')
        check_presence = db.session.query(User).filter_by(user_name=name).first()
        if check_presence:
            flash('User with that username already exists')
            return redirect(url_for('register'))
        else:
            try:
                hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
                new_user = User(user_name=name, password=hashed_password)
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                flash(f'{new_user} You were successfully logged in')
                return redirect(url_for('index'))
            except:
                flash("Couldn't add the user to the database")
                return redirect(url_for('register'))
    else:
        return render_template("register.html", form=form)


cart = {}
# img_path = None


def uploader(f):
    if f.filename != '':
        if is_allowed(f.filename):
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename))
            f.save(img_path)
            flash('file uploaded successfully', 'info')
            return img_path
        else:
            flash('incorrect file', 'error')
    else:
        flash('No selected file', 'error')


@app.route("/buy/<int:p_id>")
def buy_pr(p_id):
    global cart
    pr_to_buy = db.session.query(Product).get(p_id)
    # I just realised that I can't use sqlalchemy objects as keys, seems they can't be compared or that works wrong way
    # therefore, our cart = {Product object id: [Product object, quantity]}
    try:
        cart[pr_to_buy.p_id] = [pr_to_buy, cart[pr_to_buy.p_id][1] + 1]
    except KeyError:
        cart[pr_to_buy.p_id] = [pr_to_buy, 1]
    finally:
        print(cart)
    return redirect(url_for('products'))


@app.route("/edit/<int:p_id>", methods=['GET', 'POST'])
@login_required
@admin_only
def edit_pr(p_id):
    pr_to_upd = db.session.query(Product).get(p_id)
    if request.method == 'POST':
        # f = request.files.get('file')
        # renew text input for product
        pr_to_upd.p_category = request.form['cat']
        pr_to_upd.p_name = request.form['pname']
        pr_to_upd.p_description = request.form['pdesc']
        pr_to_upd.p_price = request.form['price']
        pr_to_upd.p_amount = request.form['amount']
        try:
            db.session.commit()
            flash(f'Product with the name {pr_to_upd.p_name} has been successfully updated.', 'info')
            return redirect(url_for('products'))
        except exc.IntegrityError:
            flash(f'Product with the name {pr_to_upd.p_name} already exists in the database.', 'error')
        # # image upload handler section
        # if f:
        #     img_path = uploader(f)
        #     if img_path:
        #         render_template('add.html', pr_image=img_path, pr=None, cat_list=CATS)
        # else:
        #     flash('Add an image for that product', 'error')
    return render_template("add.html", pr=pr_to_upd, ed=True, cat_list=CATS)


@app.route("/delete/<int:p_id>")
@login_required
@admin_only
def del_pr(p_id):
    pr_to_del = db.session.query(Product).get(p_id)
    db.session.delete(pr_to_del)
    db.session.commit()
    flash(f'Product with the name {pr_to_del.p_name} has been successfully deleted.', "info")
    return redirect(url_for('products'))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/products/<int:p_id>")
@app.route("/products")
def products(p_id=None):
    global cart
    if p_id:
        product = db.session.query(Product).get(p_id)
        return render_template("item.html", pr=product)
    all_products = db.session.query(Product).all()
    return render_template("products.html", ap=all_products, cc=cart)


@app.route("/add", methods=['GET', 'POST'])
@login_required
@admin_only
def add_product():
    global img_path
    if request.method == 'POST':
        ti_add = request.form.get('addbtn')
        f = request.files.get('file')
        # add text input for product
        if ti_add:
            p_cat = request.form['cat']
            p_name = request.form['pname']
            p_desc = request.form['pdesc']
            p_pri = request.form['price']
            p_amo = request.form['amount']
            new_product = Product(p_category=p_cat,
                                  p_name=p_name,
                                  p_description=p_desc,
                                  p_price=p_pri,
                                  p_amount=p_amo)
            try:
                db.session.add(new_product)
                db.session.commit()
                flash(f'Product with the name {p_name} has been successfully added.', 'info')
                return redirect(url_for('products'))
            except exc.IntegrityError:
                flash(f'Product with the name {p_name} already exists in the database.', 'error')
        # image upload handler section
        elif f:
            img_path = uploader(f)
            if img_path:
                render_template('add.html', pr_image=img_path, pr=None, cat_list=CATS)
        else:
            flash('Add an image for that product', 'error')
    return render_template("add.html", pr=None, cat_list=CATS)


@app.route("/flush")
def flush_cart():
    """clears any cart if that exists"""
    global cart
    cart = {}
    if current_user.is_authenticated:
        current_user.cart = {}
        db.session.commit()
        return redirect(url_for('index'))
    flash('Draft and cart have been reset.', 'info')


@app.route("/cart", methods=['GET', 'POST'])
def show_cart():
    global cart
    if current_user.is_authenticated:
        if cart:
            # if we have some draft we should update in database
            current_user.cart = cart
        else:
            # if we don't have any draft we should try to retrieve last cart from database
            cart = current_user.cart
    if request.method == 'POST':
        act_del1 = request.form.get('del1btn')
        act_conf = request.form.get('scrtbtn')
        if act_del1:
            pid_to_del = int(request.form['del1id'])
            item_to_del = cart[pid_to_del]
            if item_to_del[1] == 1:
                cart.pop(pid_to_del)
            else:
                item_to_del[1] -= 1
            flash('One item has been removed from the cart.', 'info')
        if act_conf:
            if current_user.is_authenticated:
                current_user.cart = cart
                db.session.commit()
                flash('Ready for checkout.', 'info')
                return redirect(url_for('checkout'))
            else:
                flash('Please login/register to continue.', 'error')
                return redirect(url_for('login'))
    return render_template("cart.html", cc=cart, tot=calc_total(cart))


@app.route("/checkout", methods=['GET', 'POST'])
@login_required
def checkout():
    final_cart = current_user.cart
    total = calc_total(final_cart)
    if request.method == 'POST':
        private_data = {}
        # shipping details
        fn = request.form['firstName']
        ln = request.form['lastName']
        a1 = request.form['address']
        a2 = request.form['address2']
        cy = request.form['country']
        st = request.form['state']
        zp = request.form['zip']
        private_data['a'] = {'fname': fn, 'lname': ln, 'addr1': a1, 'addr2': a2, 'country': cy, 'state': st, 'zip': zp}
        # payment processing details
        me = request.form['paymentMethod']
        na = request.form['cc-name']
        nu = request.form['cc-number']
        ex = request.form['cc-expiration']
        cv = request.form['cc-cvv']
        private_data['p'] = {'pame': me, 'ccna': na, 'ccnu': nu, 'ccex': ex, 'cccv': cv}
        # save all data for future checkmark state
        save = request.form['save-info']
        if save:
            current_user.private_details = private_data
            db.session.commit()
    return render_template("checkout.html", fc=final_cart, tot=total)


if __name__ == '__main__':
    app.run()
# debug=True