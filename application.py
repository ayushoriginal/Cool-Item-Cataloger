
from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from database_setup import Base, Category, Item, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response, jsonify
import requests

app = Flask(__name__)

engine = create_engine('sqlite:///catalogapp.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Google+ client id and application name
CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Catalog Application"


# -- User Helper Functions -- #
# Create new user and return its id
def createUser(login_session):
    newUser = User(
        name=login_session['username'],
        email=login_session['email'],
        picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


# Find user with an id and return the user
def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


# Find user with an email and return the user
def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# Check any user logged in
def user_allowed_to_browse():
    return 'username' in login_session


# Check user owner of a thing(category or item)
def user_allowed_to_edit(thing):
    return ('user_id' in login_session and
            thing.user_id == login_session['user_id'])


# Inject user_logged_in in templates to check any user logged in
@app.context_processor
def inject_user_logged_in():
    return dict(user_logged_in=user_allowed_to_browse())


# -- Category Helper Functions -- #
# Find a category using its name and return it
def category(category_name):
    return session.query(Category).filter_by(name=category_name).one()


# Return all categories in the database
def categories():
    return session.query(Category).order_by('name')


# -- Category Helper Functions -- #
# Find an item using its name and category name, then return it
def item(name, category_name):
    return session.query(Item).filter_by(
        name=name,
        category_id=category(category_name).id).one()


# Filter items with given parameters(how many, their category)
def items(count='all', category_name=None):
    # Latest 10 items
    if count == 'latest':
        return session.query(Item).order_by('id DESC').limit(10)
    elif category_name:
        current_category = category(category_name)
        filtered_items = session.query(Item).filter_by(
            category_id=current_category.id)
        # Items filtered by their category names
        return filtered_items.order_by('name')
    else:
        # All items in the database
        return session.query(Item).order_by('name')


@app.route('/login')
def showLogin():
    """Open login home page contains google+ button"""
    # Create anti-forgery state token
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    """Connect google+ account."""
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += """
        " style = "width: 80px; height: 80px;border-radius: 50%;
         -webkit-border-radius: 50%;-moz-border-radius: 50%;"> '
         """
    flash("Welcome, you are now logged in as %s." % login_session['username'])
    flash("success")
    print "done!"
    return output


@app.route('/gdisconnect')
def gdisconnect():
    """Log out from google+."""
    access_token = login_session['access_token']
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    if access_token is None:
        print 'Access Token is None'
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = ('https://accounts.google.com/o/oauth2/revoke?token=%s'
           % login_session['access_token'])
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/')
@app.route('/catalogs/')
def home():
    """
    List all of the categories, and latest items
    """
    return render_template(
        'home.html',
        all_categories=categories(),
        latest_items=items(count='latest'),
        show_categories=True)


@app.route('/catalogs/<category_name>/')
@app.route('/catalogs/<category_name>/items/')
def showCategory(category_name):
    """
    List all items in the selected category
    """
    return render_template(
        'categories/show.html',
        category_name=category_name,
        all_categories=categories(),
        filtered_items=items(category_name=category_name),
        show_categories=True)


@app.route('/catalogs/new/', methods=['GET', 'POST'])
def newCategory():
    """
    Allow logged users to create new category
    """
    # check user logged in
    if not user_allowed_to_browse():
        flash("You need to login!")
        flash("danger")
        return redirect('login')

    if request.method == 'POST':
        new_category_name = request.form['name'].strip().lower()
        if new_category_name:
            # if not blank, save it to the database
            new_category = Category(
                name=new_category_name,
                user=getUserInfo(login_session['user_id']))
            session.add(new_category)
            try:
                session.commit()
                flash("Category is successfully created.")
                flash("success")
                return redirect(
                    url_for('showCategory',
                            category_name=new_category_name))
            except IntegrityError:
                # name must be unique, so re-render form with this error
                session.rollback()
                errors = {'name': "already exists, try different name"}
                # show user-entered non-unique value in the form
                values = {'name': request.form['name']}
                return render_template(
                    'categories/new.html',
                    errors=errors,
                    values=values)
        else:
            # if it's blank, re-render form with this error
            errors = {'name': "can't be blank"}
            return render_template(
                'categories/new.html',
                errors=errors)
    else:
        # Show a form to create new category
        return render_template('categories/new.html')


@app.route('/catalogs/<category_name>/edit/', methods=['GET', 'POST'])
def editCategory(category_name):
    """
    Allow logged users to edit a category
    """
    # check user logged in
    if not user_allowed_to_browse():
        flash("You need to login!")
        flash("danger")
        return redirect('login')

    category_to_edit = category(category_name)

    # check user is owner of the category
    if not user_allowed_to_edit(category_to_edit):
        flash("""You are not authorized to edit this category, but you \
              can always create yours and then edit them if you want.""")
        flash("danger")
        return redirect('/')

    if request.method == 'POST':
        edited_category_name = request.form['name'].strip().lower()
        if edited_category_name:
            # if not blank, update it
            category_to_edit.name = edited_category_name
            session.add(category_to_edit)
            try:
                session.commit()
                flash("Category is successfully updated.")
                flash('success')
                return redirect(
                    url_for(
                        'showCategory',
                        category_name=edited_category_name))
            except IntegrityError:
                # name must be unique, so re-render form with this error
                session.rollback()
                errors = {'name': "already exists, try different name"}
                # show user-entered non-unique value in the form
                values = {'name': request.form['name']}
                return render_template(
                    'categories/edit.html',
                    category=category_to_edit,
                    errors=errors,
                    values=values)
        else:
            # if it's blank, re-render form with errors
            errors = {'name': "can't be blank"}
            return render_template(
                'categories/edit.html',
                category=category_to_edit,
                errors=errors)
    else:
        # Show a form to edit a category
        return render_template(
            'categories/edit.html',
            category=category_to_edit)


@app.route('/catalogs/<category_name>/delete/', methods=['GET', 'POST'])
def deleteCategory(category_name):
    """
    Allow logged users to delete a category (and items in it)
    """
    # check user logged in
    if not user_allowed_to_browse():
        flash("You need to login!")
        flash("danger")
        return redirect('login')

    category_to_delete = category(category_name)

    # check user is owner of the category
    if not user_allowed_to_edit(category_to_delete):
        flash("""You are not authorized to delete this category, but you \
              can always create yours and then delete them if you want.""")
        flash("danger")
        return redirect('/')

    items_to_delete = items(category_name=category_name)
    # check user is owner of the all items in that category
    for item_to_delete in items_to_delete:
        if not user_allowed_to_edit(item_to_delete):
            flash("""You are the owner of this category, but some items \
                  in that category don't belong to you. So, you \
                  can't delete the whole category. Maybe, you can try \
                  to delete your own items.""")
            flash("danger")
            return redirect('/')

    if request.method == 'POST':
        # Delete category and related items
        for item_to_delete in items_to_delete:
            session.delete(item_to_delete)
        session.delete(category_to_delete)
        try:
            session.commit()
            flash("Category is successfully deleted.")
            flash('success')
            return redirect('/')
        except:
            session.rollback()
            return "An unknown error occured!"
    else:
        # Show a confirmation to delete
        return render_template(
            'categories/delete.html',
            category_name=category_name)


@app.route('/catalogs/<category_name>/items/<item_name>/')
def showItem(category_name, item_name):
    """
    Show details of selected item
    """
    item_to_show = item(item_name, category_name)
    return render_template('items/show.html', item=item_to_show)


@app.route('/catalogs/<category_name>/items/new/', methods=['GET', 'POST'])
def newItem(category_name):
    """
    Allow logged users to create an item
    """
    # check user logged in
    if not user_allowed_to_browse():
        flash("You need to login!")
        flash("danger")
        return redirect('login')

    if request.method == 'POST':
        new_item_name = request.form['name'].strip().lower()
        new_item_description = request.form['description'].strip()
        if new_item_name and new_item_description:
            # if not blank, save to database
            try:
                # if same item in that category, re-render with error
                item(name=new_item_name, category_name=category_name)
                errors = {
                    'name': 'another item has same name, and same category'}
                params = {
                    'name': new_item_name,
                    'description': new_item_description}
                return render_template(
                        'items/new.html',
                        category_name=category_name,
                        errors=errors,
                        params=params)
            except:
                new_item = Item(
                    name=new_item_name,
                    description=new_item_description,
                    category=category(category_name),
                    user=getUserInfo(login_session['user_id']))
                session.add(new_item)
                session.commit()
                flash("Item is successfully created.")
                flash('success')
                return redirect(
                    url_for(
                        'showItem',
                        category_name=category_name,
                        item_name=new_item_name))
        else:
            errors = {}
            # store user-entered data to show them in re-rendered form
            params = {'name': '', 'description': ''}
            if new_item_name:
                params['name'] = new_item_name
            else:
                errors['name'] = "can't be blank"

            if new_item_description:
                params['description'] = new_item_description
            else:
                errors['description'] = "can't be blank"

            return render_template(
                'items/new.html',
                category_name=category_name,
                errors=errors,
                params=params)
    else:
        # Show a form to create new item
        return render_template(
            'items/new.html',
            category_name=category_name,
            params={'name': '', 'description': ''})


@app.route(
    '/catalogs/<category_name>/items/<item_name>/edit/',
    methods=['GET', 'POST'])
def editItem(category_name, item_name):
    """
    Allow logged users to edit an item
    """
    # check user logged in
    if not user_allowed_to_browse():
        flash("You need to login!")
        flash("danger")
        return redirect('login')

    item_to_edit = item(item_name, category_name)

    # check user is owner of the item
    if not user_allowed_to_edit(item_to_edit):
        flash("""You are not authorized to edit this item, but you \
              can always create yours and then edit them if you want.""")
        flash("danger")
        return redirect('/')

    if request.method == 'POST':
        # Update item
        edited_item_name = request.form['name'].strip().lower()
        edited_item_description = request.form['description'].strip()
        if edited_item_name and edited_item_description:
            item_to_edit.name = edited_item_name
            item_to_edit.description = edited_item_description
            session.add(item_to_edit)
            try:
                session.commit()
                flash("Item is successfully updated.")
                flash('success')
                return redirect(
                    url_for(
                        'showItem',
                        category_name=category_name,
                        item_name=edited_item_name))
            except IntegrityError:
                # Item name is non-uniqueI
                session.rollback()
                errors = {'name': 'another item has same name'}
                params = {'name': edited_item_name,
                          'description': edited_item_description}
                return render_template(
                    'items/edit.html',
                    category_name=category_name,
                    item_name=item_name,
                    errors=errors,
                    params=params)
        else:
            errors = {}
            # store user-entered data to show them in re-rendered form
            params = {'name': '', 'description': ''}
            if edited_item_name:
                params['name'] = edited_item_name
            else:
                errors['name'] = "can't be blank"

            if edited_item_description:
                params['description'] = edited_item_description
            else:
                errors['description'] = "can't be blank"

            return render_template('items/edit.html',
                                   category_name=category_name,
                                   item_name=item_name,
                                   errors=errors,
                                   params=params)
    else:
        # Show a form to edit item
        return render_template(
            'items/edit.html',
            category_name=category_name,
            item_name=item_name,
            params={'name': item_to_edit.name,
                    'description': item_to_edit.description})


@app.route(
    '/catalogs/<category_name>/items/<item_name>/delete/',
    methods=['GET', 'POST'])
def deleteItem(category_name, item_name):
    """
    Allow logged users to delete an item
    """
    # check user logged in
    if not user_allowed_to_browse():
        flash("You need to login!")
        flash('danger')
        return redirect('login')

    item_to_delete = item(item_name, category_name)

    # check user is towner of the item
    if not user_allowed_to_edit(item_to_delete):
        flash("""You are not authorized to delete this item, but you \
              can always create yours and then edit them if you want.""")
        flash("danger")
        return redirect('/')

    if request.method == 'POST':
        # Delete item
        session.delete(item_to_delete)
        try:
            session.commit()
            flash("Item is successfully deleteed.")
            flash('success')
            return redirect(
                url_for('showCategory', category_name=category_name))
        except:
            session.rollback()
            return "An unknown error occured!"
    else:
        # Show a confirmation to delete
        return render_template(
            'items/delete.html',
            category_name=category_name,
            item_name=item_name)


# JSON API for catalogs
@app.route('/catalogs/JSON')
def CatalogsJSON():
    json_categories = categories()
    return jsonify(Categories=[c.serialize for c in json_categories])


# JSON API for catalog
@app.route('/catalogs/<category_name>/items/JSON')
def CatalogItemsJSON(category_name):
    json_items = items(category_name=category_name)
    return jsonify(CategoryItems=[i.serialize for i in json_items])


# JSON API for item
@app.route('/catalogs/<category_name>/items/<item_name>/JSON')
def ItemJSON(category_name, item_name):
    json_item = item(item_name, category_name)
    return jsonify(CategoryItem=json_item.serialize)


if __name__ == '__main__':
    app.secret_key = 'iamsosecret'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
