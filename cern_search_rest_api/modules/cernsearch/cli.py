#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This file is part of CERN Search.
# Copyright (C) 2018-2019 CERN.
#
# Citadel Search is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Click command-line utilities."""

import click
from cern_search_rest_api.modules.cernsearch.indexer import CernSearchRecordIndexer
from flask.cli import with_appcontext
from invenio_indexer.tasks import process_bulk_queue
from invenio_pidstore.models import PersistentIdentifier, PIDStatus


def abort_if_false(ctx, param, value):
    """Abort command is value is False."""
    if not value:
        ctx.abort()


@click.group()
def utils():
    """Misc management commands."""


@utils.command('runindex')
@click.option(
    '--delayed', '-d', is_flag=True, help='Run indexing in background.')
@click.option(
    '--concurrency', '-c', default=1, type=int,
    help='Number of concurrent indexing tasks to start.')
@click.option('--queue', '-q', type=str,
              help='Name of the celery queue used to put the tasks into.')
@click.option('--version-type', help='Elasticsearch version type to use.')
@click.option(
    '--raise-on-error/--skip-errors', default=True,
    help='Controls if Elasticsearch bulk indexing errors raise an exception.')
@with_appcontext
def run(delayed, concurrency, version_type=None, queue=None,
        raise_on_error=True):
    """Run bulk record indexing."""
    if delayed:
        celery_kwargs = {
            'kwargs': {
                'version_type': version_type,
                'es_bulk_kwargs': {'raise_on_error': raise_on_error},
            }
        }
        click.secho(
            'Starting {0} tasks for indexing records...'.format(concurrency),
            fg='green')
        if queue is not None:
            celery_kwargs.update({'queue': queue})
        for c in range(0, concurrency):
            process_bulk_queue.apply_async(**celery_kwargs)
    else:
        click.secho('Indexing records...', fg='green')
        CernSearchRecordIndexer(version_type=version_type).process_bulk_queue(
            es_bulk_kwargs={'raise_on_error': raise_on_error})


@utils.command('reindex')
@click.option('--yes-i-know', is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Do you really want to reindex all records?')
@click.option('-t', '--pid-type', multiple=True, required=True)
@with_appcontext
def reindex(pid_type):
    """Reindex all records.

    :param pid_type: Pid type.
    """
    click.secho('Sending records to indexing queue ...', fg='green')

    query = (x[0] for x in PersistentIdentifier.query.filter_by(
        object_type='rec', status=PIDStatus.REGISTERED
    ).filter(
        PersistentIdentifier.pid_type.in_(pid_type)
    ).values(
        PersistentIdentifier.object_uuid
    ))
    CernSearchRecordIndexer().bulk_index(query)
    click.secho('Execute "run" command to process the queue!',
                fg='yellow')
