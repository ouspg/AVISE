.. _contributing:


Contributing to AVISE
===========================

We warmly welcome contributions from the community! AVISE is an open-source project,
and its continued improvement depends on the involvement of developers like you. Whether you
are fixing a bug, adding a new feature, or improving documentation, your contributions help
make AVISE better for everyone.

This page descibes the general process of contributing code to AVISE. If you are looking for
more detailed instructions on how to extend AVISE by contributing a new Security Evaluation Test,
Pipeline, or Connector, check out the respective contribution pages: :ref:`contributing_set`,
:ref:`_contributing_pipeline`, :ref:`_contributing_connector`.

Getting in Touch
----------------

If you have questions, ideas, or need guidance before contributing, the best way to reach
the AVISE development team is through the `AVISE Discord channel <https://discord.gg/CebeeMUqSP>`_.
The community and core developers are active there and happy to assist new contributors,
discuss proposed changes, or help troubleshoot issues.

We look forward to your contributions and thank you for helping improve AVISE!

Contribution Workflow
---------------------

To contribute code to AVISE, please follow the steps below:

- **Fork the repository** — Navigate to the `AVISE GitHub repository <https://github.com/ouspg/avise>`_ and click the *Fork* button to create your own copy of the project under your GitHub account.
- **Clone your fork** — Clone your forked repository to your local machine using ``git clone``.
- **Create a feature branch** — Create a new branch for your changes (e.g. ``git checkout -b feature/my-new-feature``) to keep your work isolated from the ``main`` branch.
- **Make your changes** — Implement your fix, feature, or improvement. Ensure your code follows the project's coding style and conventions, and include unit tests where applicable.
- **Commit and push** — Commit your changes with a clear and descriptive commit message, then push your branch to your forked repository.
- **Open a Pull Request** — Navigate to the original AVISE repository on GitHub and open a Pull Request (PR) from your feature branch. Provide a clear description of what your changes do and why they are needed.

Review and Merging Process
--------------------------

Once a Pull Request is submitted, it will be reviewed by the AVISE developers. Automated tests
are ran on the code to ensure it follows the project's coding style and passes all unit tests.
The developers will examine the code for overall alignment
with the project's goals. Reviewers may request changes or clarifications before approval.
Once the Pull Request is approved and all checks pass, it will be merged into the main
repository by a maintainer.
