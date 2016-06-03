import os
import json
from django.test import TestCase
from django.http import QueryDict
from django.conf import settings
from rest_framework.test import APIRequestFactory, force_authenticate
from tutelary.models import Policy

from accounts.tests.factories import UserFactory
from organization.tests.factories import OrganizationFactory, ProjectFactory
from .factories import ResourceFactory
from ..views import api

from buckets.test.utils import ensure_dirs
from buckets.test.storage import FakeS3Storage
path = os.path.dirname(settings.BASE_DIR)

ensure_dirs()
storage = FakeS3Storage()
file = open(path + '/resources/tests/files/image.jpg', 'rb')
file_name = storage.save('image.jpg', file)

clauses = {
    'clause': [
        {
            'effect': 'allow',
            'object': ['project/*/*'],
            'action': ['resource.*']
        },
        {
            'effect': 'allow',
            'object': ['resource/*/*/*'],
            'action': ['resource.*']
        }
    ]
}


class ProjectResourcesTest(TestCase):
    def setUp(self):
        self.project = ProjectFactory.create()
        self.resources = ResourceFactory.create_batch(
            2, content_object=self.project)
        self.denied = ResourceFactory.create(content_object=self.project,
                                             project=self.project)
        ResourceFactory.create()
        self.view = api.ProjectResources.as_view()
        self.url = '/v1/organizations/{org}/projects/{prj}/resources/'

        clauses['clause'].append({
            'effect': 'deny',
            'object': ['resource/*/*/' + self.denied.id],
            'action': ['resource.*']
        })

        policy = Policy.objects.create(
            name='allow',
            body=json.dumps(clauses))
        self.user = UserFactory.create()
        self.user.assign_policies(policy)

    def _get(self, org, prj, query=None, user=None, status=None, count=None):
        if user is None:
            user = self.user

        url = self.url.format(org=org, prj=prj)
        if query is not None:
            url += '?' + query
        request = APIRequestFactory().get(url)
        if query is not None:
            setattr(request, 'GET', QueryDict(query))
        force_authenticate(request, user=user)
        response = self.view(request, organization=org, project=prj).render()
        content = json.loads(response.content.decode('utf-8'))
        if status is not None:
            assert response.status_code == status
        if count is not None:
            assert len(content) == count
        return content

    def _post(self, org, prj, data, user=None, status=None, count=None):
        if user is None:
            user = self.user

        request = APIRequestFactory().post(
            self.url.format(org=org, prj=prj), data, format='json'
        )
        force_authenticate(request, user=user)
        response = self.view(request, organization=org, project=prj).render()
        content = json.loads(response.content.decode('utf-8'))
        if status is not None:
            assert response.status_code == status
        if count is not None:
            assert self.project.resources.count() == count
        return content

    def test_list_resources(self):
        content = self._get(self.project.organization.slug,
                            self.project.slug,
                            status=200,
                            count=2)
        returned_ids = [r['id'] for r in content]
        assert all(res.id in returned_ids for res in self.resources)

    def test_get_full_list_organization_does_not_exist(self):
        project = ProjectFactory.create()
        content = self._get('some-org', project.slug, status=404)
        assert content['detail'] == "Project not found."

    def test_get_full_list_project_does_not_exist(self):
        organization = OrganizationFactory.create()
        content = self._get(organization.slug, '123abd', status=404)
        assert content['detail'] == "Project not found."

    def test_get_full_list_with_unauthorized_user(self):
        self._get(self.project.organization.slug,
                  self.project.slug,
                  status=200,
                  user=UserFactory.create(),
                  count=0)

    def test_add_resource(self):
        data = {
            'name': 'New resource',
            'description': '',
            'file': file_name,
            'original_file': 'image.png'
        }
        self._post(self.project.organization.slug,
                   self.project.slug,
                   data,
                   status=201,
                   count=4)

    def test_add_resource_with_unauthorized_user(self):
        data = {
            'name': 'New resource',
            'description': '',
            'file': file_name
        }
        self._post(self.project.organization.slug,
                   self.project.slug,
                   data,
                   status=403,
                   count=3,
                   user=UserFactory.create())

    def test_add_exisiting_resource(self):
        new_resource = ResourceFactory.create()
        data = {'id': new_resource.id}
        self._post(self.project.organization.slug,
                   self.project.slug,
                   data,
                   status=201,
                   count=4)
        assert new_resource in self.project.resources

    def test_add_invalid_resource(self):
        data = {
            'name': '',
            'description': '',
            'file': 'http://example.com/somefile/'
        }
        response = self._post(self.project.organization.slug,
                              self.project.slug,
                              data,
                              status=400,
                              count=3)
        assert 'name' in response

    def test_search_for_file(self):
        not_found = storage.save('bild.jpg', file)
        project = ProjectFactory.create()
        ResourceFactory.create_from_kwargs([
            {'content_object': project, 'file': file_name},
            {'content_object': project, 'file': file_name},
            {'content_object': project, 'file': not_found}
        ])
        self._get(project.organization.slug,
                  project.slug,
                  query='search=image',
                  status=200,
                  count=2)

    def test_filter_active(self):
        project = ProjectFactory.create()
        ResourceFactory.create_from_kwargs([
            {'content_object': project, 'archived': True},
            {'content_object': project, 'archived': True},
            {'content_object': project, 'archived': False},
        ])
        self._get(project.organization.slug,
                  project.slug,
                  query='archived=True',
                  status=200,
                  count=2)

    def test_ordering(self):
        project = ProjectFactory.create()
        ResourceFactory.create_from_kwargs([
            {'content_object': project, 'name': 'A'},
            {'content_object': project, 'name': 'B'},
            {'content_object': project, 'name': 'C'},
        ])
        content = self._get(project.organization.slug,
                            project.slug,
                            query='ordering=name',
                            status=200,
                            count=3)
        names = [resource['name'] for resource in content]
        assert(names == sorted(names))

    def test_reverse_ordering(self):
        project = ProjectFactory.create()
        ResourceFactory.create_from_kwargs([
            {'content_object': project, 'name': 'A'},
            {'content_object': project, 'name': 'B'},
            {'content_object': project, 'name': 'C'},
        ])
        content = self._get(project.organization.slug,
                            project.slug,
                            query='ordering=-name',
                            status=200,
                            count=3)
        names = [resource['name'] for resource in content]
        assert(names == sorted(names, reverse=True))


class ProjectResourcesDetailTest(TestCase):
    def setUp(self):
        self.project = ProjectFactory.create()
        self.resource = ResourceFactory.create(content_object=self.project)
        self.view = api.ProjectResourcesDetail.as_view()
        self.url = '/v1/organizations/{org}/projects/{prj}/resources/{res}'
        policy = Policy.objects.create(
            name='allow',
            body=json.dumps(clauses))
        self.user = UserFactory.create()
        self.user.assign_policies(policy)

    def _get(self, org, prj, res, user=None, status=None, count=None):
        if user is None:
            user = self.user

        request = APIRequestFactory().get(self.url.format(org=org, prj=prj,
                                                          res=res))
        force_authenticate(request, user=user)
        response = self.view(request, organization=org, project=prj,
                             resource=res).render()
        content = json.loads(response.content.decode('utf-8'))
        if status is not None:
            assert response.status_code == status
        if count is not None:
            assert len(content) == count
        return content

    def _patch(self, org, prj, res, data, user=None, status=None, count=None):
        if user is None:
            user = self.user

        request = APIRequestFactory().patch(
            self.url.format(org=org, prj=prj, res=res), data, format='json'
        )
        force_authenticate(request, user=user)
        response = self.view(request, organization=org, project=prj,
                             resource=res).render()
        content = json.loads(response.content.decode('utf-8'))
        if status is not None:
            assert response.status_code == status
        if count is not None:
            assert self.project.resources.count() == count
        return content

    def _put(self, org, prj, res, user=None, status=None, count=None):
        if user is None:
            user = self.user

        request = APIRequestFactory().put(
            self.url.format(org=org, prj=prj, res=res), format='json'
        )
        force_authenticate(request, user=user)
        response = self.view(request, organization=org, project=prj,
                             resource=res).render()
        content = json.loads(response.content.decode('utf-8'))
        if status is not None:
            assert response.status_code == status
        if count is not None:
            assert self.project.resources.count() == count
        return content

    def test_get_resource(self):
        content = self._get(self.project.organization.slug,
                            self.project.slug,
                            self.resource.id,
                            status=200)
        assert content['id'] == self.resource.id

    def test_get_resource_with_unauthorized_user(self):
        content = self._get(self.project.organization.slug,
                            self.project.slug,
                            self.resource.id,
                            status=403,
                            user=UserFactory.create())
        assert 'id' not in content

    def test_get_resource_from_org_that_does_not_exist(self):
        content = self._get('some-org',
                            self.project.slug,
                            self.resource.id,
                            status=404)
        assert content['detail'] == "Project not found."

    def test_get_resource_from_project_that_does_not_exist(self):
        content = self._get(self.project.organization.slug,
                            'some-prj',
                            self.resource.id,
                            status=404)
        assert content['detail'] == "Project not found."

    def test_update_resource(self):
        data = {'name': 'Updated'}
        content = self._patch(self.project.organization.slug,
                              self.project.slug,
                              self.resource.id,
                              data,
                              status=200)
        assert content['id'] == self.resource.id
        self.resource.refresh_from_db()
        assert self.resource.name == data['name']

    def test_update_resource_with_unauthorized_user(self):
        data = {'name': 'Updated'}
        content = self._patch(self.project.organization.slug,
                              self.project.slug,
                              self.resource.id,
                              data,
                              status=403,
                              user=UserFactory.create())
        assert 'id' not in content
        self.resource.refresh_from_db()
        assert self.resource.name != data['name']

    def test_update_invalid_resource(self):
        data = {'name': ''}
        content = self._patch(self.project.organization.slug,
                              self.project.slug,
                              self.resource.id,
                              data,
                              status=400)
        assert 'name' in content

    def test_archive_resource(self):
        data = {'archived': True}
        content = self._patch(self.project.organization.slug,
                              self.project.slug,
                              self.resource.id,
                              data,
                              status=200)
        assert content['id'] == self.resource.id
        self.resource.refresh_from_db()
        assert self.resource.archived is True

    def test_archive_resource_with_unauthorized_user(self):
        data = {'archived': True}
        content = self._patch(self.project.organization.slug,
                              self.project.slug,
                              self.resource.id,
                              data,
                              status=403,
                              user=UserFactory.create())
        assert 'id' not in content
        self.resource.refresh_from_db()
        assert self.resource.archived is False

    def test_unarchive_resource(self):
        self.resource.archived = True
        self.resource.save()
        data = {'archived': False}
        content = self._patch(self.project.organization.slug,
                              self.project.slug,
                              self.resource.id,
                              data,
                              status=200)
        assert content['id'] == self.resource.id
        self.resource.refresh_from_db()
        assert self.resource.archived is False

    def test_unarchive_resource_with_unauthorized_user(self):
        self.resource.archived = True
        self.resource.save()
        data = {'archived': False}
        content = self._patch(self.project.organization.slug,
                              self.project.slug,
                              self.resource.id,
                              data,
                              status=403,
                              user=UserFactory.create())
        assert 'id' not in content
        self.resource.refresh_from_db()
        assert self.resource.archived is True