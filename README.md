# User-Management
This project is a powerful, tenant-based user management system that allows for the management of platforms, projects, roles, rights, and members. Built using Django, this system is designed to be highly customizable and scalable, making it suitable for a wide range of applications.

#### [Full Api Documentaion click Here](https://documenter.getpostman.com/view/25199832/2sAXjGdEMD#58d9a911-f02c-4b49-a2ec-e194b7833492)

## Features
- Platform Management: Create and manage multiple platforms within the system.
- Project Management: Organize platforms into projects with specific configurations.
- Role-Based Access Control: Assign roles with specific rights and permissions to users.
- User Management: Manage users across different platforms and projects with detailed control over their roles and rights.
- Authentication: Secure login methods including password and OTP-based authentication.

## Technologies Used
- Django: A high-level Python Web framework that encourages rapid development.
- MySQL: For database management, used to store all user, platform, project, and role data.
- Postman: Collection included for testing API endpoints

## Setup Instructions
### Prerequisites
- Python 3.8+
- Django 3.2+
- MySQL 5.7+
- Postman (for API testing)

## Installation

- Clone the Repository:

```
git clone https://github.com/muhammedrahil/User-Management.git
```
- Install Dependencies:
```
pip install -r requirements.txt
```

## About Project

### STEP 1 - Tenant Initialisation

For each Platform there may be multiple domain urls associated. For each domain url it is easily identify us the tenant on which tenant it is associated.


### STEP 2 - Tenant Management

Tenant Management inclusive of the Platforms, Projects, Roles, User Types, Rights, Domain mapped urls.

- Platform - Platform can be used as a Tenant. (But if the project requirement is having multiple tenants alone under one single entity can be satisfied by our super platform seeder. In case if the project requirements may have more than one platform, then use this platform management apis).
  - Platform can have their very own Roles & Rights.
  - Platform should compuslory have their own user types.
  - Platform can contains more than one tenants and each tenant may have separate users. (Project entity is the one which we are talking about the Tenants).

- Project - Projects can be considered as a Tenants.
  - Project can have their very own Roles & Rights.
  - Project can have their very own users
  - Project should compuslory have their own user types.
  - Project can contains more than one tenants and each tenant may have separate users.

- Rights - Rights Management
  - Before kickstarting Roles/ User Type management, Rights should be created at must.

- User Type Management
  - User Type is used to group all the users in a single tenant.
  - Example: I have Managers, Staffs, Administrators.
  - Among these user types there is different Role users may exists, such as Administrators user type contains Admin, Super Admin.
  - Managers User Type may contains different managers, Operations Manager, Project Manager, Product Manager (this can be created in role and the user type should be mapped as Manager).


- Roles Management
  - Roles Creation - Rights should be mapped in the Roles.
  - For creating roles rights is required.

- Domain mapped URLs.
  - Why we are using Domain mapped urls?
    - Our application url is https://app.example.com
    - All the tenants should logging in https://app.example.com
      - But if we are allowing tenants to use their very own domain preference then we may require to know which domain url is mapped with which tenant.
      - For this purpose we definitely need this domain url.
      - Mainly it should refer the frontend url.

    - And if this usermanagement may used by different projects such as
      - app.instance.com - It is super platform or platform
        - It may contains multiple tenants (projects).

      - app.illustration.com - It is super platform or platform
        - It may contains multiple tenants (projects).

      - app.example.com - It is super platform or platform
        - It may contains multiple tenants (projects).

      - For this purpose we have planned to have the domain urls included with the Authentication.
     

### STEP 3 - User Management

- Member Management.
- For creation of the Member it is mandatory to have the following fields.
  - platform_id
  - project_id
  - email_id - It should be unique across the project.
  - user_type
  - role
  - first_name

- Member Platform is the unqiue id and it should be considered as user_id or member_id across the projects and platforms.

# Database Diagram

![Databsa-Diagram.png](https://github.com/user-attachments/assets/182b9835-90db-41df-9921-21d30e93eeb9)
