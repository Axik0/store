from flask import Flask, render_template, request, url_for, flash, redirect, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import exc

# file.py has been changed "from collections.abc import Iterable" in sqlalchemy_imageattach!!
from sqlalchemy_imageattach.entity import Image, image_attachment
from sqlalchemy_imageattach.stores.fs import HttpExposedFileSystemStore
from sqlalchemy_imageattach.context import store_context

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
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzzzz'
Bootstrap(app)

CATS = ['Merch', 'Household', 'SSS tier']

# cart = {}
# temp_img_path = None

# file upload folder
app.config['UPLOAD_FOLDER'] = 'static/temp'
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1000 * 10
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


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

# Connect to Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mystore.db'
# this has to be turned off to prevent flask-sqlalchemy framework from tracking events and save resources
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# I have to create this key to use CSRF protection for form
db = SQLAlchemy(app)

# file storage implementation
# new folder in path (path/productpics) will be created (and filled) automatically even if it doesn't exist
hfs_store = HttpExposedFileSystemStore(path='static/',
                                       prefix='images/',
                                       host_url_getter=lambda:'http://{0}/'.format('127.0.0.1:5000'))
# At least for now, only httP, NOT HTTPS as stated in sqlalchemy docs!!!!!
app.wsgi_app = hfs_store.wsgi_middleware(app.wsgi_app)
# print(app.config['SERVER_NAME'])

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
    # delete purchases or db!!!!
    purchases = db.Column(db.PickleType)
    cart = db.Column(db.PickleType)

    # 1-Many bi-directional bond
    u_orders = relationship("Order", back_populates="client")

    # I just want to return a string with custom printable representation of an object, overrides standard one
    def __repr__(self):
        return f'<User_{self.id}: {self.user_name}>'


class Order(db.Model):
    __tablename__ = "orders"
    o_id = db.Column(db.Integer, primary_key=True)
    o_date = db.Column(db.Date, default=date.today())
    o_contents = db.Column(db.PickleType)
    o_state = db.Column(db.Integer, nullable=False)
    # 1-Many bi-directional bond
    u_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    client = relationship("User", back_populates="u_orders")


class Product(db.Model):
    __tablename__ = "products"
    p_id = db.Column(db.Integer, primary_key=True)
    p_category = db.Column(db.String(20), nullable=False)
    p_name = db.Column(db.String(50), unique=True, nullable=False)
    p_description = db.Column(db.String(200), nullable=False)
    p_price = db.Column(db.Integer, nullable=False)
    p_amount = db.Column(db.Integer, nullable=False)

    # 1-1? bi-directional bond
    p_image = image_attachment('ProductPicture', back_populates="product")

    def __repr__(self):
        """rrrrrrrepresentacion"""
        return f'<Product_{self.p_id}: {self.p_name}>'

    # implement some kind of storage here
    def store_to_p_image(self, temp_path):
        """extracts the file from temp location by path and add/change product's image using that"""
        with store_context(hfs_store):
            with open(temp_path, 'rb') as f:
                self.p_image.from_file(f)
            db.session.commit()

    def upload_p_image(self, f):
        """unused as I use temp folder for upload in my algorithm"""
        with store_context(hfs_store):
            self.p_image.from_file(f)
            db.session.commit()

    def get_pi_path(self):
        """get url to the image in storage"""
        with store_context(hfs_store):
            # print(self.p_image.locate())
            return self.p_image.locate()

    def del_pi(self):
        """I just had to create this one here in order to delete product without errors"""
        with store_context(hfs_store):
            self.p_image.delete()


class ProductPicture(db.Model, Image):
    """Product picture model."""
    __tablename__ = 'productpics'
    product_id = db.Column(db.Integer, db.ForeignKey('products.p_id'), primary_key=True)

    # 1-1? bi-directional bond
    product = relationship('Product', back_populates="p_image")


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


# {user_id1:[temp_image_path, temp_cart], ...}
active_session = {}
# {random user id: cart dict}
anonymous_session = {}
anon_ids = [i for i in range(1000)]


def update_as(t_path, t_cart={}):
    """updates cart draft for a particular user"""
    global active_session, anonymous_session, anon_ids
    if current_user.is_authenticated:
        active_session[current_user.id] = [t_path, t_cart]
    else:
        # provide random id to each user in order to keep his cart for him
        try:
            rand_id = random.choice(anon_ids)
            anon_ids.remove(rand_id)
        except IndexError:
            # what if we run out of 1000 anonymous ids? Let's prevent an excessive server load
            print('Unable to maintain that many users.')


def flush_as(f_cart=False):
    """deletes cart draft for a particular user"""
    global active_session
    active_session[current_user.id][0] = None
    if f_cart:
        active_session[current_user.id][1] = {}


@app.route("/flush")
def flush_cart(dbonly=True):
    """clears any type of cart if that exists"""
    global active_session
    # clear session cart = draft for this user, registered or not
    if not dbonly:
        flush_as(True)
    if current_user.is_authenticated:
        # clear cart for this user (saved in db)
        current_user.cart = {}
        db.session.commit()
        return redirect(url_for('index'))
    flash('Draft and cart have been reset.', 'info')


@app.route("/")
def index():
    return render_template("index.html")


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
                # when user logs in, he must be added to active session with initial temp vars
                update_as(None)
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
    global active_session
    try:
        # remove this user from active session
        active_session.pop(current_user.id)
        # but save his cart in db for the next time
        current_user.cart = active_session[current_user.id][1]
        db.session.commit()
    except:
        print('You forgot to log out.')
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
                flash(f'{new_user} You have logged in successfully.')
                return redirect(url_for('index'))
            except:
                flash("Couldn't add the user to the database")
                return redirect(url_for('register'))
    else:
        return render_template("register.html", form=form)


@app.route("/products/<int:p_id>")
@app.route("/products")
def products(p_id=None):
    global active_session
    cart = active_session[current_user.id][1]
    if p_id:
        product = db.session.query(Product).get(p_id)
        return render_template("item.html", pr=product)
    all_products = db.session.query(Product).all()
    # I use the cart here just to show quantity of each product on page if it is in user's cart
    return render_template("products.html", ap=all_products, cc=cart)


@app.route("/buy/<int:p_id>")
def buy_pr(p_id):
    global active_session
    cart = active_session[current_user.id][1]
    pr_to_buy = db.session.query(Product).get(p_id)
    # I just realised that I can't use sqlalchemy objects as keys, seems they can't be compared or that works wrong way
    # therefore, our cart = {Product object id: [Product object, quantity]}
    try:
        # try to reach and if this product exists in the cart, update its quantity only
        cart[pr_to_buy.p_id] = [pr_to_buy, cart[pr_to_buy.p_id][1] + 1]
    except KeyError:
        cart[pr_to_buy.p_id] = [pr_to_buy, 1]
    finally:
        update_as(None, cart)
    return redirect(url_for('products'))


@app.route("/cart", methods=['GET', 'POST'])
def show_cart():
    global active_session
    # check not registered user!
    cart = active_session[current_user.id][1]
    if current_user.is_authenticated and not cart:
        # if we don't have any draft we should try to retrieve last cart from database
        cart = current_user.cart
    if request.method == 'POST':
        act_del1 = request.form.get('del1btn')
        act_conf = request.form.get('scrtbtn')
        if act_del1:
            if current_user.is_authenticated:
                # from now on, we are working with draft, we don't need to keep the db cart anymore
                flush_cart()
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
                # we don't need the cart draft any more
                flush_as(True)
                flash('Ready for checkout.', 'info')
                return redirect(url_for('checkout'))
            else:
                flash('Please login/register to continue.', 'error')
                # his cart=draft is going to be deleted on login, thus needs external exception for non-registered users
                return redirect(url_for('login'))
        # in case we deleted an item from the cart and came back
        update_as(None, cart)
    return render_template("cart.html", cc=cart, tot=calc_total(cart) if cart else {})


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

        # # !!!THIS SILENTLY BREAKS EVERYTHING UNLESS YOU PUT THAT CHECKMARK!!!
        # save all data for future checkmark state
        # save = request.form['save-info']
        # if save:
        #     current_user.private_details = private_data
        #     db.session.commit()

        # final_cart = {Product object id: [Product object, quantity], ...}
        # I don't want to store whole product objects in orders as they could mutate,
        # contents = [{Product object id: quantity, ...}, total]
        new_order = Order(o_contents=[{k: v[1] for k, v in final_cart.items()}, total], o_state=0, client=current_user)
        db.session.add(new_order)
        db.session.commit()
        flash('Your order has been registered', 'info')
        # remove existing cart from database
        flush_cart()
        return redirect(url_for('my_orders'))
    return render_template("checkout.html", fc=final_cart, tot=total)


@app.route("/order/<int:o_id>")
@app.route("/orders")
@login_required
def my_orders(o_id=None):
    if o_id:
        o = db.session.query(Order).get(o_id)
        occ = {k: [db.session.query(Product).get(k), v] for k, v in o.o_contents[0].items()}
        return render_template("order.html", cc=occ, tot=o.o_contents[1], o=o)
    orders = current_user.u_orders
    return render_template("orders.html", ord=orders)


@app.route("/control")
@login_required
@admin_only
def control_panel():
    # let's get all registered users (excluding admin)
    users = db.session.query(User).filter(User.id != 1).all()
    # create a dictionary of all users with a total income from their orders
    ctr_data = {u: sum([o.o_contents[1][0] if u.u_orders else 0 for o in u.u_orders]) for u in users}
    return render_template("control.html", cd=ctr_data)


@app.route("/add", methods=['GET', 'POST'])
@login_required
@admin_only
def add_product():
    global active_session
    if request.method == 'POST':
        # we should have an image path when we upload and come back via POST
        temp_img_path = active_session[1][0]
        f = request.files.get('file')
        ti_add = request.form.get('addbtn')

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
        # add text input for product
        if ti_add:
            if temp_img_path:
                try:
                    db.session.add(new_product)
                    db.session.commit()
                    db.session.refresh(new_product)
                    new_product.store_to_p_image(temp_img_path)
                    # print(new_product.get_pi_path())
                    # success => we don't need an img path any more
                    flush_as()
                    flash(f'Product with the name {p_name} has been successfully added.', 'info')
                    return redirect(url_for('products'))
                except exc.IntegrityError:
                    flash(f'Product with the name {p_name} already exists in the database.', 'error')
            else:
                flash('Add an image for that product', 'error')
                return render_template('add.html', pr=new_product, cat_list=CATS)
        # image upload handler section
        elif f:
            if f.filename != '':
                if is_allowed(f.filename):
                    temp_img_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename))
                    f.save(temp_img_path)
                    # as we upload something, we should add the path to our active session too
                    update_as(temp_img_path)
                    flash('file uploaded successfully', 'info')
                    return render_template('add.html', pr_image=temp_img_path, pr=new_product, cat_list=CATS)
                else:
                    flash('incorrect file', 'error')
            else:
                flash('No selected file', 'error')
    # when we GET this url without POST we should take care of possibly leftover draft
    flush_as()
    return render_template("add.html", pr=None, cat_list=CATS)


@app.route("/edit/<int:p_id>", methods=['GET', 'POST'])
@login_required
@admin_only
def edit_pr(p_id):
    global active_session
    pr_to_upd = db.session.query(Product).get(p_id)
    if request.method == 'POST':
        # we MAY have an image path when we upload and come back via POST
        temp_img_path = active_session[1][0]
        # renew text input for product
        f = request.files.get('file')
        ti_conf = request.form.get('confbtn')
        p_cat = request.form['cat']
        p_name = request.form['pname']
        p_desc = request.form['pdesc']
        p_pri = request.form['price']
        p_amo = request.form['amount']
        temp_product = Product(p_category=p_cat, p_name=p_name, p_description=p_desc, p_price=p_pri, p_amount=p_amo)
        # add text input for product
        if ti_conf:
            try:
                pr_to_upd.p_category = temp_product.p_category
                pr_to_upd.p_name = temp_product.p_name
                pr_to_upd.p_description = temp_product.p_description
                pr_to_upd.p_price = temp_product.p_price
                pr_to_upd.p_amount = temp_product.p_amount
                db.session.commit()
                flash(f'Product with the name {pr_to_upd.p_name} has been successfully updated.', 'info')
                if temp_img_path:
                    db.session.refresh(pr_to_upd)
                    pr_to_upd.store_to_p_image(temp_img_path)
                    flash("Product's image has been changed.", 'info')
                else:
                    flash("Product's image has left unchanged.", 'info')
                return redirect(url_for('products'))
            except exc.IntegrityError:
                flash(f'Product with the name {pr_to_upd.p_name} already exists in the database.', 'error')
        # image upload handler section
        elif f:
            if f.filename != '':
                if is_allowed(f.filename):
                    temp_img_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename))
                    # print(secure_filename(f.filename), app.config['UPLOAD_FOLDER'], temp_img_path)
                    f.save(temp_img_path)
                    # as we upload something, we should add the path to our active session too
                    update_as(temp_img_path)
                    flash('file uploaded successfully', 'info')
                    # '/' must be here otherwise it adds /edit/ and results in error
                    return render_template('add.html', pr_image='/'+temp_img_path, pr=temp_product, ed=True, cat_list=CATS)
                else:
                    flash('incorrect file', 'error')
            else:
                flash('No selected file', 'error')
    # when we GET this url without POST we should take care of possibly leftover draft
    flush_as()
    return render_template("add.html", pr_image=pr_to_upd.get_pi_path(), pr=pr_to_upd, ed=True, cat_list=CATS)


@app.route("/delete/<int:p_id>")
@login_required
@admin_only
def del_pr(p_id):
    pr_to_del = db.session.query(Product).get(p_id)
    pr_to_del.del_pi()
    db.session.delete(pr_to_del)
    db.session.commit()
    flash(f'Product with the name {pr_to_del.p_name} has been successfully deleted.', "info")
    return redirect(url_for('products'))


if __name__ == '__main__':
    app.run()
# debug=True
