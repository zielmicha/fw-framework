import fw.core
import fw.login
import fw.util
import fw.login.social

class Friends(fw.core.Widget):
	view = 'profile.fwml:friends'
	
	opt = fw.core.Attr(default='none')
	
	def get_view_attrs(self):
		friends = self.session.user.friends
		using = filter(lambda s: s.is_using, friends)
		not_using = filter(lambda s: not s.is_using, friends)
		return dict(friends=using + not_using, opt=self.opt)
	
	@fw.core.action()
	def invite(self, user):
		name = self.session.user.name
		msg = fw.login.social.Message(
			text=self.translate('invite') % dict(name=name),
			link='/invited/' + self.session.userid
		)
		self.session.user.notify_friend(user, msg)

fw.core.widget(name='friends')(Friends)