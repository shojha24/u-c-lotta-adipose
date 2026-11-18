DEV NOTE: api is currently deprecated; UCLA has greatly changed their dining hall menu format, so the API will not be active before adapting scraper to new format. aws resource usage paused to save money.

scraper functionality for retrieving menu items, nutrition info, metadata for 10 dining locations
aws ec2 instance calling scraper once a day to retrieve menu items and store in s3 bucket as json
api gateway/lambda handler for retrieving menu items requested by user; implement extensive caching to prevent from too many s3 reads
api FORMERLY accessible via https://5xjgg3ho6c.execute-api.us-west-2.amazonaws.com/

todo:

- adapt to new UCLA dining hall menu format
- add truck and ASUCLA menus/hours
- add gym hours
- create online api documentation
- make python package as api wrapper
- make cool project with this!!
