"""
    View functions for dolphin project
    Author: YuanBao
    Email: wenkaiyuan123@gmail.com
"""

from django.http import HttpResponse
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from django.contrib import auth
from ipmi.models import Request, RequestHost, Info
from django.utils import timezone
from xmlrpclib import ServerProxy
from settings import REMOTE_SERVER_IP, REMOTE_SERVER_PORT, LOCAL_IP, LOCAL_PORT
from django.template import loader, Context
import csv,json,threading

def login_view(request):
    """
        Handle business logic initially
        Corresponding URL : (ip:port/)
    """
    if request.user.is_authenticated(): 
        return HttpResponseRedirect('/index.html')
    else:
        return render_to_response('login.html')

def index_view(request):
    """
        Return index page for valid users
            and return default page for invalid visitors
        Corresponding URL : (ip:port/index.html)
    """
    if request.user.is_authenticated():
        return render_to_response('index.html')
    else:
        return HttpResponseRedirect('/')

@csrf_exempt
def validate_view(request):
    """
        Check wthether the visitor is valid
        Corresponding URL : (ip:port/login.html)
    """
    if request.method != 'POST':
        return Http404('Only POSTs are allowed')
    if "username" in request.POST:
        username = request.POST["username"]
    else:
        username = ""

    if "password" in request.POST:
        password = request.POST["password"]
    else:
        password = ""

    admin_user = auth.authenticate(username=username, password=password)
    if admin_user is not None and admin_user.is_active:
        auth.login(request, admin_user)
        return HttpResponse("/index.html")
    else:
        return HttpResponse("error")

def logout_view(request):
    """
        Log out the visitor
        Corresponding URL : (ip:port/logout.html)
    """
    auth.logout(request)
    return HttpResponseRedirect('/')


def history_view(request):
    """
        Return the page of history CMDs for users
        Corresponding URL : (ip:port/history.html)
    """
    if request.user.is_authenticated():
        cmd_his_list = Request.objects.all()
        return render_to_response('history.html', {'cmd_his_list': cmd_his_list})
    else:
        return HttpResponseRedirect('/')


request_status = {}
request_condition = {}

@csrf_exempt
def sel_query_view(request):
    """
        TODO (Kaiyuan)
    """
    global request_status
    global request_condition

    if request.user.is_authenticated():
        request_type = int(request.POST["request_type"])
        if request_type == 1:   ## First query
            sel_request = Request(start_time=timezone.now(), status=0, detail='')
            sel_request.save()
            request_id = str(sel_request.id)
            request.session["rid"] = request_id

            request_class = int(request.POST["request_class"])  ##single-cmd or multi-cmd
            
            if request_class == 1:
                username, password, ip = (
                    request.POST["username"], 
                    request.POST["password"],
                    request.POST["ip_addr"]
                )
                sel_host = RequestHost(
                    ip_addr=ip, username=username, 
                    password=password, start_time=timezone.now(), 
                    request_id=sel_request.id, status=0, detail='')
                sel_host.save()
            
            elif request_class == 2:
                cmd_string = request.POST["cmd_list"]
                cmd_list = json.loads(cmd_string)
                for cmd in cmd_list:
                    sel_host = RequestHost(
                        ip_addr=cmd["ip_addr"], username=cmd["username"], 
                        password=cmd["password"], start_time=timezone.now(), 
                        request_id=sel_request.id, status=0, detail='')
                    sel_host.save()

            server_addr = "http://%s:%s" % (REMOTE_SERVER_IP, REMOTE_SERVER_PORT)
            dolphind_cb_url = "http://%s:%s/callback.html/" % (LOCAL_IP, LOCAL_PORT)

            request_condition[request_id] = threading.Semaphore(0)
        
            dolphind = ServerProxy(server_addr)
            dolphind.request(sel_request.id, dolphind_cb_url)
            request_condition[request_id].acquire()
            return HttpResponse(request_status[request_id])

        elif request_type == 2:
            request_id = str(request.session["rid"])
            request_condition[request_id].acquire()
            return HttpResponse(request_status[request_id])

        elif request_type == 3:
            request_id = str(request.session["rid"])
            ipmi_entry_list = Info.objects.filter(request_id=request_id)
            return render_to_response('sel_table.html', {'ipmi_entry_list': ipmi_entry_list})


@csrf_exempt
def dolphind_cb_view(request):
    global request_status
    global request_condition
    request_id, status, succ_counter = (str(request.GET["request_id"]), 
                                        int(request.GET["status"]),
                                        int(request.GET["success_count"]))
    if status == 2:
        if succ_counter != 0:
            request_status[request_id] = status
        else:
            request_status[request_id] = 3
    else:
        request_status[request_id] = status
    request_condition[request_id].release()


def export_csv_view(request):
    if request.user.is_authenticated():
        if "rid" in request.session:
            request_id = request.session["rid"]
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="sel_list.csv"'

            writer = csv.writer(response)

            ipmi_entry_list = Info.objects.filter(request_id=request_id)
            for entry in ipmi_entry_list:
                print entry.sel_info
                details = json.loads(entry.sel_info)
                row = [ details[key] for key in details ]
                writer.writerow(row)
            return response

@csrf_exempt
def reload_history_view(request):
    if request.user.is_authenticated():
        cmd_his_list = Request.objects.all()
        return render_to_response('cmd_table.html', {'cmd_his_list': cmd_his_list})
