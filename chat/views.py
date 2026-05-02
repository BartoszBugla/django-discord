from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Profile, Channel, ChannelMember, Message, Reaction
from .forms import RegisterForm, ProfileForm, ChannelForm, MessageForm


def _flash_form_errors(request, form):
    """Dodaje komunikaty Django forms jako wiadomości flash (po polsku)."""
    if not getattr(form, "errors", None):
        return
    for err in form.non_field_errors():
        messages.error(request, err)
    for field_name, error_list in form.errors.items():
        if field_name == "__all__":
            continue
        field = form.fields.get(field_name)
        label = field.label if field and field.label else field_name
        for err in error_list:
            messages.error(request, f"{label}: {err}")


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
            except IntegrityError:
                form.add_error(
                    "email",
                    "Ten adres e-mail jest już zarejestrowany.",
                )
            else:
                profile, _ = Profile.objects.get_or_create(user=user)
                profile.is_online = True
                profile.last_seen_at = timezone.now()
                profile.save(update_fields=["is_online", "last_seen_at"])
                login(request, user)
                return redirect('chat:home')
    else:
        form = RegisterForm()
    return render(request, 'chat/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(
                    request,
                    "To konto zostało zablokowane przez administratora. Logowanie jest niemożliwe.",
                )
                return render(request, 'chat/login.html')
            login(request, user)
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.is_online = True
            profile.last_seen_at = timezone.now()
            profile.save(update_fields=["is_online", "last_seen_at"])
            next_url = request.POST.get('next', request.GET.get('next', '/'))
            return redirect(next_url)
        inactive = User.objects.filter(username=username).first()
        if (
            inactive is not None
            and not inactive.is_active
            and inactive.check_password(password)
        ):
            messages.error(
                request,
                "To konto zostało zablokowane przez administratora. Logowanie jest niemożliwe.",
            )
        else:
            messages.error(request, "Nieprawidłowa nazwa użytkownika lub hasło.")
    return render(request, 'chat/login.html')


@login_required
def logout_view(request):
    profile = getattr(request.user, "profile", None)
    if profile:
        profile.is_online = False
        profile.last_seen_at = None
        profile.save(update_fields=["is_online", "last_seen_at"])
    logout(request)
    return redirect('chat:login')


@login_required
def home(request):
    channels = Channel.objects.all()
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/home.html', {
        'channels': channels,
        'all_channels': all_channels,
    })


@login_required
def profile_view(request, user_id):
    viewed_user = get_object_or_404(User, pk=user_id)
    profile, _ = Profile.objects.get_or_create(user=viewed_user)
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/profile.html', {
        'viewed_user': viewed_user,
        'profile': profile,
        'all_channels': all_channels,
    })


@login_required
def edit_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil został zaktualizowany.")
            return redirect('chat:profile', user_id=request.user.id)
        _flash_form_errors(request, form)
    else:
        form = ProfileForm(instance=profile)
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/edit_profile.html', {
        'form': form,
        'all_channels': all_channels,
    })


@login_required
def create_channel(request):
    if request.method == 'POST':
        form = ChannelForm(request.POST)
        if form.is_valid():
            channel = form.save(commit=False)
            channel.tworca = request.user
            channel.save()
            ChannelMember.objects.create(user=request.user, channel=channel)
            return redirect('chat:channel', channel_id=channel.id)
        _flash_form_errors(request, form)
    else:
        form = ChannelForm()
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/create_channel.html', {
        'form': form,
        'all_channels': all_channels,
    })


@login_required
def channel_view(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    is_member = ChannelMember.objects.filter(user=request.user, channel=channel).exists()

    if not is_member:
        return redirect('chat:join_channel', channel_id=channel.id)

    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.autor = request.user
            msg.channel = channel
            msg.save()
            from chat.inbox_notify import notify_channel_message_saved

            notify_channel_message_saved(msg)
            return redirect('chat:channel', channel_id=channel.id)
        _flash_form_errors(request, form)

    wiadomosci = Message.objects.filter(channel=channel).select_related('autor', 'autor__profile')
    members = ChannelMember.objects.filter(channel=channel).select_related('user', 'user__profile')
    all_channels = Channel.objects.filter(members__user=request.user)
    emojis = ['👍', '👎', '❤️', '😂', '😮', '😢', '🔥', '🎉']

    all_reactions = Reaction.objects.filter(message__channel=channel)
    grouped = {}
    for r in all_reactions:
        key = (r.message_id, r.emoji)
        if key not in grouped:
            grouped[key] = {'emoji': r.emoji, 'count': 0, 'mine': False}
        grouped[key]['count'] += 1
        if r.user_id == request.user.id:
            grouped[key]['mine'] = True

    reactions_map = {}
    for (msg_id, emoji), data in grouped.items():
        reactions_map.setdefault(msg_id, []).append(data)

    member_ids = ChannelMember.objects.filter(channel=channel).values_list(
        "user_id", flat=True
    )
    addable_users = (
        User.objects.exclude(pk__in=member_ids)
        .select_related("profile")
        .order_by("username")
    )
    can_add_members = request.user == channel.tworca or _is_admin(request.user)

    return render(request, 'chat/channel.html', {
        'channel': channel,
        'wiadomosci': wiadomosci,
        'members': members,
        'all_channels': all_channels,
        'emojis': emojis,
        'reactions_map': reactions_map,
        'addable_users': addable_users,
        'can_add_members': can_add_members,
    })


@login_required
def join_channel(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    ChannelMember.objects.get_or_create(user=request.user, channel=channel)
    return redirect('chat:channel', channel_id=channel.id)


@login_required
def add_channel_member(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    if not ChannelMember.objects.filter(user=request.user, channel=channel).exists():
        messages.error(request, "Brak dostępu do kanału.")
        return redirect('chat:home')
    if request.user != channel.tworca and not _is_admin(request.user):
        messages.error(request, "Brak uprawnień do dodawania członków.")
        return redirect('chat:channel', channel_id=channel.id)

    raw_id = request.POST.get('user_id', '').strip()
    if not raw_id:
        messages.error(request, "Wybierz użytkownika.")
        return redirect('chat:channel', channel_id=channel.id)
    try:
        target = User.objects.get(pk=int(raw_id))
    except (ValueError, User.DoesNotExist):
        messages.error(request, "Nieprawidłowy użytkownik.")
        return redirect('chat:channel', channel_id=channel.id)

    if ChannelMember.objects.filter(user=target, channel=channel).exists():
        messages.info(request, "Ten użytkownik jest już na tym kanale.")
        return redirect('chat:channel', channel_id=channel.id)

    ChannelMember.objects.create(user=target, channel=channel)
    messages.success(request, f"Dodano użytkownika „{target.username}” do kanału.")
    return redirect('chat:channel', channel_id=channel.id)


@login_required
def delete_channel(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    if request.user == channel.tworca or _is_admin(request.user):
        channel.delete()
        messages.success(request, "Kanał został usunięty.")
    else:
        messages.error(request, "Brak uprawnień do usunięcia kanału.")
    return redirect('chat:home')


@login_required
def dm_list(request):
    sent = Message.objects.filter(autor=request.user, channel__isnull=True).values_list('odbiorca', flat=True)
    received = Message.objects.filter(odbiorca=request.user, channel__isnull=True).values_list('autor', flat=True)
    user_ids = set(list(sent) + list(received))
    users = User.objects.filter(id__in=user_ids)
    all_users = User.objects.exclude(id=request.user.id)
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/dm_list.html', {
        'users': users,
        'all_users': all_users,
        'all_channels': all_channels,
    })


@login_required
def dm_view(request, user_id):
    other_user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.autor = request.user
            msg.odbiorca = other_user
            msg.save()
            from chat.inbox_notify import notify_dm_message_saved

            notify_dm_message_saved(msg)
            return redirect('chat:dm', user_id=other_user.id)
        _flash_form_errors(request, form)

    wiadomosci = Message.objects.filter(
        Q(autor=request.user, odbiorca=other_user) |
        Q(autor=other_user, odbiorca=request.user),
        channel__isnull=True
    ).select_related('autor', 'autor__profile')
    all_channels = Channel.objects.filter(members__user=request.user)

    return render(request, 'chat/dm.html', {
        'other_user': other_user,
        'wiadomosci': wiadomosci,
        'all_channels': all_channels,
    })


def _is_moderator_or_admin(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile.role in ('admin', 'moderator') or user.is_superuser


@login_required
def delete_message(request, message_id):
    msg = get_object_or_404(Message, pk=message_id)

    if request.user == msg.autor or _is_moderator_or_admin(request.user):
        redirect_url = request.POST.get('next', '/')
        msg.delete()
        messages.success(request, "Wiadomość została usunięta.")
        return redirect(redirect_url)
    return redirect('chat:home')


@login_required
def add_reaction(request, message_id):
    msg = get_object_or_404(Message, pk=message_id)
    emoji = request.POST.get('emoji', '')
    if emoji:
        reaction, created = Reaction.objects.get_or_create(
            user=request.user, message=msg, emoji=emoji
        )
        if not created:
            reaction.delete()
    next_url = request.POST.get('next', '/')
    return redirect(next_url)


def _is_admin(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile.role == 'admin' or user.is_superuser


@login_required
def change_role(request, user_id):
    if not _is_admin(request.user):
        messages.error(request, "Brak uprawnień.")
        return redirect('chat:home')

    target = get_object_or_404(User, pk=user_id)
    target_profile, _ = Profile.objects.get_or_create(user=target)
    new_role = request.POST.get('role', 'user')
    if new_role in ('admin', 'moderator', 'user'):
        target_profile.role = new_role
        target_profile.save()
        messages.success(
            request,
            f"Rola użytkownika {target.username} została ustawiona na: {target_profile.get_role_display()}.",
        )
    return redirect('chat:profile', user_id=user_id)


@login_required
def notifications_settings(request):
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/notifications_settings.html', {
        'all_channels': all_channels,
    })


@login_required
def search_view(request):
    query = (request.GET.get('q') or '').strip()
    users = User.objects.none()
    channels = Channel.objects.none()
    if query:
        users = (
            User.objects.filter(
                Q(username__icontains=query) | Q(email__icontains=query)
            )
            .exclude(pk=request.user.pk)
            .order_by('username')[:50]
        )
        channels = Channel.objects.filter(nazwa__icontains=query).order_by('nazwa')[:50]
    member_ids = set(
        ChannelMember.objects.filter(user=request.user).values_list('channel_id', flat=True)
    )
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/search.html', {
        'query': query,
        'users': users,
        'channels': channels,
        'channel_member_ids': member_ids,
        'all_channels': all_channels,
    })


@login_required
def search_api(request):
    q = (request.GET.get('q') or '').strip()
    if len(q) < 1:
        return JsonResponse({'users': [], 'channels': []})
    users = list(
        User.objects.filter(
            Q(username__icontains=q) | Q(email__icontains=q)
        )
        .exclude(pk=request.user.pk)
        .values('id', 'username')
        .order_by('username')[:12]
    )
    member_ids = set(
        ChannelMember.objects.filter(user=request.user).values_list('channel_id', flat=True)
    )
    channels = []
    for ch in Channel.objects.filter(nazwa__icontains=q).order_by('nazwa')[:12]:
        channels.append({
            'id': ch.id,
            'nazwa': ch.nazwa,
            'is_member': ch.id in member_ids,
        })
    return JsonResponse({'users': users, 'channels': channels})


@login_required
def leave_channel(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    ChannelMember.objects.filter(user=request.user, channel=channel).delete()
    messages.success(request, f"Opuściłeś kanał „{channel.nazwa}”.")
    return redirect('chat:home')


@login_required
def presence_status(request, user_id):
    get_object_or_404(User, pk=user_id)
    profile, _ = Profile.objects.get_or_create(user_id=user_id)
    return JsonResponse({"appears_online": profile.appears_online})


@login_required
def admin_toggle_user_active(request, user_id):
    """Wlacza / wylacza konto (User.is_active) — blokada na poziomie calej aplikacji."""
    if request.method != 'POST':
        return redirect('chat:admin_users')
    if not _is_admin(request.user):
        messages.error(request, "Brak uprawnień.")
        return redirect('chat:home')
    if user_id == request.user.id:
        messages.error(request, "Nie możesz wyłączyć własnego konta w ten sposób.")
        return redirect('chat:admin_users')
    target = get_object_or_404(User, pk=user_id)
    if target.is_superuser and not request.user.is_superuser:
        messages.error(request, "Brak uprawnień do zmiany tego konta.")
        return redirect('chat:admin_users')
    action = (request.POST.get('action') or '').strip()
    if action == 'deactivate':
        target.is_active = False
        target.save(update_fields=['is_active'])
        messages.success(
            request,
            f"Konto „{target.username}” zostało zablokowane — użytkownik nie może się zalogować.",
        )
    elif action == 'activate':
        target.is_active = True
        target.save(update_fields=['is_active'])
        messages.success(request, f"Konto „{target.username}” zostało odblokowane.")
    else:
        messages.error(request, "Nieprawidłowa akcja.")
    return redirect('chat:admin_users')


@login_required
def admin_users(request):
    if not _is_admin(request.user):
        messages.error(request, "Brak uprawnień.")
        return redirect('chat:home')

    users = User.objects.select_related('profile').all()
    channels = Channel.objects.all()
    all_channels = Channel.objects.filter(members__user=request.user)
    return render(request, 'chat/admin_users.html', {
        'users': users,
        'channels': channels,
        'all_channels': all_channels,
    })


def custom_404(request, exception):
    return render(request, 'chat/404.html', status=404)
