from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Base, Category, Item, User

engine = create_engine('sqlite:///catalogapp.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

categories = [
    ['soccer',
        [{'name': 'two shinguards',
          'description': 'Description of two shinguards'},
         {'name': 'shinguards',
          'description': 'Description of singuards'},
         {'name': 'jersey',
          'description': 'Description of jersey'},
         {'name': 'soccer cleats',
          'description': 'Description of soccer cleats'}]],
    ['hockey',
        [{'name': 'stick',
          'description': 'Description of hockey stick'}]],
    ['snowboarding',
        [{'name': 'goggles',
          'description': 'Description of goggles'},
         {'name': 'snowboard',
          'description': 'Description of snowboard'}]],
    ['frisbee',
        [{'name': 'frisbee',
          'description': 'Description of frisbee'}]],
    ['baseball',
        [{'name': 'bat',
          'description': 'Description of bat'}]]
]

current_user = User(name="System User", email="system@test.com")
session.add(current_user)
session.commit()

for category in categories:
    current_category = Category(name=category[0], user=current_user)
    session.add(current_category)
    session.commit()

    for item in category[1]:
        current_item = Item(name=item['name'],
                            description=item['description'],
                            category=current_category,
                            user=current_user)
        session.add(current_item)
        session.commit()

print "Database seeding complete!"
