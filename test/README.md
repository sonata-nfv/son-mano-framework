# test/

This folder should contain the high-level entrypoints for our test scripts (automatically triggered by the CI system).

## Available tests:
* test_son-mano-base.sh: Runs RabbitMQ in a first Docker container and executes the unittests in son-mano-base/ in a second container.
* ...