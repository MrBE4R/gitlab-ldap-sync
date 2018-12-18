
# gitlab-ldap-sync

Python project to sync LDAP/Active Directory Groups into GitLab.

The script will create the missing LDAP groups into gitlab and sync membership of all LDAP groups. 

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

This project has been tested on CentOS 7.6 with GitLab 11.5.* and OpenLDAP and Active Directory.

```
Python        : 3.4.9
pip3          : 8.1.2
python-gitlab : 1.6.0
python-ldap   : 3.1.0
```

### Installing

You could either install requirements system wide or use virtual environment / conda, choose your poison.

To get this up and running you just need to do the following :

* Clone the repo
```bash
git clone https://github.com/MrBE4R/gitlab-ldap-sync.git
```
* Install requirements
```bash
pip3 install -r ./gitlab-ldap-sync/requirements.txt
```
* Edit config.json with you values
```bash
EDITOR ./gitlab-ldap-sync/config.json
```
* Start the script and enjoy your sync users and groups being synced
```bash
cd ./gitlab-ldap-sync && ./gitlab-ldap-sync.py
```

You should get something like this :
```bash
Initializing gitlab-ldap-sync.
Done.
Connecting to GitLab
Done.
Connecting to LDAP
Done.
Getting all groups from GitLab.
Done.
Getting all groups from LDAP.
Done.
Groups currently in GitLab : < G1 >, < G2 >, < G3 >, < G4 >, < G5 >, < P1 >, < P2 >, < P3 >
Groups currently in LDAP : < G1 >, < G2 >, < G3 >, < G4 >, < G5 >, < G6 >, < G7 > 
Syncing Groups from LDAP.
Working on group <Group Display Name> ...
|- Group already exist in GitLab, skiping creation.
|- Working on group's members.
|  |- User <User Display Name> already in gitlab group, skipping.
|  |- User <User Display Name> already in gitlab group, skipping.
[...]
|- Done.
[...]
Done
```

You could add the script in a cron to run it periodically.
## Deployment

How to configure config.json
```json5
{
  "syncInterval": "10m",                              // Actually not using it for now
  "log": "/tmp/gitlab-ldap-sync.log",                 // Actually not using it for now
  "gitlab": {
    "api": "https://gitlab.example.com",              // Url of your GitLab 
    "private_token": "xxxxxxxxxxxxxxxxxxxx",          // Token generated in GitLab for an user with admin access
    "oauth_token": "",
    "ldap_provider":"",                               // Name of your LDAP provider in gitlab.yml
    "create_user": true                               // Should the script create the user in GitLab
  },
  "ldap": {
    "url": "ldaps://ldap.loc",                        // URL to your ldap / active directory
    "users_base_dn": "ou=users,dc=example,dc=com",    // Where we should look for users
    "groups_base_dn": "ou=groupss,dc=example,dc=com", // Where we should look for groups
    "bind_dn": "login",                               // User to log with
    "password": "password",                           // Password of the user
    "group_attribute": "",                            // Actually not using it for now
    "group_prefix": ""                                // Actually not using it for now
  }
}
```
You should use ```private_token``` or ```oauth_token``` but not both. Check [the gitlab documentation](https://docs.gitlab.com/ce/user/profile/personal_access_tokens.html#creating-a-personal-access-token) for how to generate the personal access token.

```create_user``` If set to true, the script will create the users in gitlab and add them in the corresponding groups. Be aware that gitlab will send a mail to every new users created.
## TODO

* Use async search to avoid errors with large LDAP
* Maybe implement sync interval directly in the script to avoid using cron or systemd
* Use a true logging solution (no more silly print statements)
* Implement ```group_attribute``` and ```group_prefix``` to allow the selection of the groups to sync (avoid syncing every groups into gitlab)
* your suggestions
## Built With

* [Python](https://www.python.org/)
* [python-ldap](https://www.python-ldap.org/en/latest/)
* [python-gitlab](https://python-gitlab.readthedocs.io/en/stable/)

## Contributing

Please read [CONTRIBUTING.md](https://gist.github.com/PurpleBooth/b24679402957c63ec426) for details on our code of conduct, and the process for submitting pull requests to us.

## Authors

* **Jean-François GUILLAUME (Jeff MrBear)** - *Initial work* - [PurpleBooth](https://github.com/PurpleBooth)

See also the list of [contributors](https://github.com/MrBE4R/gitlab-ldap-sync/contributors) who participated in this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

## Acknowledgments

* Hat tip to anyone whose code was used