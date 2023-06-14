# User Manual

## Skill Sets & Skill Set Groups

### Skill sets

Skill sets allow you to check if a character has a set of skills. This is most often used to see if a character can fly a ship fitting, but it can also be used more general, e.g. to see if a character can build a specific capital.

Skill sets are a list of skills with minimum and (optionally) recommended levels for each skill.

You can define skill sets manually by adding skills with their levels. Or you can create them from existing fittings or skill plans. For example if you create them from a fitting, Member Audit will automatically determine which skills at which minimum level are required to fly that fitting and create the skill set accordingly. If you want you can then also add recommended levels for each skill.

Skill sets are shown for each character on the character viewer including the information if that particular character has all the skills or which skills are missing. This way a recruiter can quickly see, what doctrine ships an applicant can fly. Or an alliance member can see which skills he might need to train to fly a particular doctrine ship.

Another way to see which characters have specific skill sets is on the reports page. There all skill sets are shown that a character has the skills for.

### Skill groups

Skill sets can be organized into skill set groups. A common skill set group would be a doctrine. Note that skill sets can belong to multiple skill set groups at the same time (or to none).

### Editing skill sets & skill groups

Skill sets and skill groups are be created and modified on the admin site.

It is possible to give a user narrow access for just the purpose of editing skill sets & skill groups. For that a user needs to following permissions (e.g. defined through a group) and the user also needs to be granted the "staff" right, which is a user property.

- memberaudit | eve ship type | Can view eve ship type
- memberaudit | eve skill type | Can view eve skill type
- memberaudit | skill set | Can add skill set
- memberaudit | skill set | Can change skill set
- memberaudit | skill set | Can delete skill set
- memberaudit | skill set | Can view skill set
- memberaudit | skill set group | Can add skill set group
- memberaudit | skill set group | Can change skill set group
- memberaudit | skill set group | Can delete skill set group
- memberaudit | skill set group | Can view skill set group
- memberaudit | skill | Can add skill
- memberaudit | skill | Can change skill
- memberaudit | skill | Can delete skill
- memberaudit | skill | Can view skill

## Compliance Groups

The compliance group feature enables you to prevent users who are not fully compliant - i.e. who have not yet added all their characters to Member Audit - from getting access to a service. This can be an effective incentive for users to add all their characters.

Compliance groups are designated Alliance Auth groups. Users are automatically assigned or removed from these groups depending on their current compliance status.

To require compliance for accessing a service, just add the respective permissions to the compliance groups.

You can define multiple compliance groups. This can be useful if you want to configure individual service access for each state, e.g. by having a compliance group for each state.

The feature is enabled as soon as at least one compliance group exists. Once enabled, a user will be notified when he gains are looses his compliance status. To disable the feature you can either delete all compliance group designations or the compliance groups themselves.

To create a compliance group please follow these steps:

1. Create a new internal group under Group Management / Groups
1. Add the permissions you want to grant to compliant users only
1. Designate that group as compliance group by adding it under Member Audit / Compliance Group Designations

A user is compliant when the following two criteria are both true:

- User has access to Member Audit (i.e. has the access permission)
- User has registered all his characters to Member Audit

```{Note}
Only internal groups can be enabled as compliance groups.
```

```{important}
Once you have enabled a group as compliance group any user assignments will be handled automatically by Member Audit and Alliance Auth.
```
