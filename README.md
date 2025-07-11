whats done:

scraper functionality for retrieving menu items, nutrition info, metadata for 10 dining locations
aws ec2 instance calling scraper once a day to retrieve menu items and store in s3 bucket as json

todo:

add lambda functions for caching and serving data from s3 bucket
use existing api for activity levels to serve activity levels of each dining hall:
- de neve: https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=866
- bplate: https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=864
- epic covel: https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=864
- bcafe: https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=867
- cafe 1919: https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=867
- epic ackerman: https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=874
- rende: https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=870
- drey: https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=869
- study: https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=871
- feast: https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=872
make python package as api wrapper
make cool project with this!!