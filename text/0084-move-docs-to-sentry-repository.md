- Start Date: 2023-04-06
- RFC Type: decision
- RFC PR: -
- RFC Status: approved
- RFC Driver: [Priscila Oliveira](https://github.com/priscilawebdev)
- RFC Approver: [Frontend TSC Committee](https://www.notion.so/sentry/2349fa7dfc5a4e9b95eda0961725896d)

# Introduction

Currently, our documentation is located in the [sentry-docs repository](https://github.com/getsentry/sentry-docs), where we always maintain two versions of the getting started guide for each platform we support. One version is more complete and is the one we display on our website and the second is a shorter version that we fetch and render in our app's onboarding flow.

<aside>
ℹ️ The technical writing team usually helps us review the documents, but those who add and maintain them are usually the engineers working on these platforms (SDKs).

</aside>

# Summary

The mechanism we currently use to add getting-started documents for our platforms is difficult to maintain and not scalable.

The purpose of this RFC is to discuss more practical, scalable, and dynamic solutions for creating and rendering documents that we display for each platform in our onboarding.

# Motivation

We recently added a new user interface to our onboarding for the React platform, allowing users to choose which Sentry products they would like to have in their project (Performance monitoring and Session Replay). The code snippets that users often copy and paste into their SDKs are updated according to the selected products.

In order for this experiment to dynamically render code snippets based on product selection, we had to add 3 very similar but different extra markdown files to our sentry-docs repository, [here is the PR](https://github.com/getsentry/sentry-docs/pull/6497). Also, for these new markdowns to be rendered correctly in Sentry, some more changes were needed in different functions, showing us that this way of rendering dynamic content is not maintainable and scalable.

As we want to go ahead and add a selection of products to all javascript platforms and in the future to other platforms as well, we are looking at other better ways to do this.

# Background

1. There is [a script](https://github.com/getsentry/sentry-docs/blob/16f1e2b115e50a677e03e19a71ad3b3b5fd9df51/src/gatsby/onPostBuild.ts#L132) that we use to convert the markdown files from the [sentry-docs](https://github.com/getsentry/sentry-docs) to a JSON that is fetched later on by our Sentry application.
2. These markup files cannot render content dynamically and if we need something more dynamic we have to create different versions for each change, [here is an example](https://github.com/getsentry/sentry-docs/pull/6497). As we add different versions of the content for each platform, [we also have to update the script](https://github.com/getsentry/sentry-docs/blob/16f1e2b115e50a677e03e19a71ad3b3b5fd9df51/src/gatsby/onPostBuild.ts#L76-L129) so that it creates the JSON in the correct format for these files.
3. Sentry has an automation in place that fetches the JSON file mentioned above and based on that generates other JSON files for each platform, storing them in the folder `integration-docs`. This automation is dependent on the JSON format coming from the [sentry-docs](https://github.com/getsentry/sentry-docs) repository, and removing the `index.md` for instance effectively removes the platform root and breaks the deployments, [here is an example of when we had to reverse a PR because of this](https://github.com/getsentry/sentry-docs/pull/6434).
4. On top of that, the [platforms](https://github.com/getsentry/sentry/blob/1902d6be1ee18c4ce22c0c09f6a6a1fa18128fad/static/app/data/platforms.tsx#L29-L72) list used in the front end have to be filtered to not display wrong/extra platforms in the onboarding, project creation, and in other places.

# Options considered

1. Gradually move the get started docs for the onboarding from the sentry-docs repository to sentry, where we'll write everything in MDX.

   This helps with a few things:

   a) That way, we can write everything in React and possibly reuse components from our component library, like alerts.

   b) This will allow us to be more consistent with styles used in our application, remove several functions we have in place for the current mechanism, and use best practices.

   We can still ask the docs team for reviews on our Pull Requests when needed.

2. Change the docs repo to a monorepo and publish the onboarding instructions as a javascript library.

   Then we can write first in docs - and use dependabot to automatically update this dependency whenever needed. We could even hard pin to latest.

   Source of truth only written once, and in a single place!

   This helps with a few things:

   a) Makes it much easier to add docs changes, we just need to npm link to test out onboarding instruction changes locally

   b) We can use whatever libraries we want for mdx, and even write tests for them without needing to burden the sentry frontend repo.

   In addition this opens us up to expanding the docs monorepo to publish other packages that other consumers could use.

3. Do you have other ideas? Please share with us!

# Drawbacks

1. If we go with option one (1) proposed above, we will have to live with 2x different mechanisms for a while until we port all the documentation over to Sentry and we will have to install a few `@mdx-js/*` dependencies
2. Right now to update onboarding instructions you can do it in a single PR in the docs repo. If we make the second change proposed (2), it will mean that devs have to first merge docs, and after update Sentry. If any of these two are delayed/out of sync, it could be confusing to users who don't understand why the product shows something different that the actual docs themselves

# Conclusion

[As per the TSC Frontend Meeting on Tuesday, April 4, 2023](https://www.notion.so/sentry/2349fa7dfc5a4e9b95eda0961725896d), we discussed the problem and proposed solutions described in this RFC and concluded that we would like to proceed with the first proposal. We have yet to inform the docs team about this decision, but initially we would like to gradually move the onboarding docs from the sentry-docs repository to the sentry repository and no longer use markdown, but MDX or pure react components. A proof of concept will be created and shared with Frontend TSC members.
