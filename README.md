note: api is pretty limited during summer quarter, will have to see if it still brings full functionality for the dining halls that are open

whats done:

scraper functionality for retrieving menu items, nutrition info, metadata for 10 dining locations
aws ec2 instance calling scraper once a day to retrieve menu items and store in s3 bucket as json
built api (accessible [here](https://5xjgg3ho6c.execute-api.us-west-2.amazonaws.com/))

todo:

- figure out the domain routing stuff in aws to connect to
- add truck and ASUCLA menus/hours
- add gym hours
- create online api documentation
- make python package as api wrapper
- make cool project with this!!
