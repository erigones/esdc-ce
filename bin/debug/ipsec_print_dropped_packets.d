#!/usr/sbin/dtrace -FCs

#define      SADB_EXT_MAX                    27
#include <inet/ipsec_info.h>

ip_drop_packet:entry
/((mblk_t *)arg0)->b_datap->db_type == M_DATA &&
 (((mblk_t *)arg0)->b_wptr - ((mblk_t *)arg0)->b_rptr) >= 28 &&
  (*(((mblk_t *)arg0)->b_rptr) & 0xF0) == 0x40/

{
	self->hdr_len = (*(((mblk_t *)arg0)->b_rptr) & 0x0F) * 4;
	self->ipproto = *(((mblk_t *)arg0)->b_rptr+9);

	printf("\nIPsec dropped an %s IPv4 packet.\n",
			arg1 ? "inbound" : "outbound");
	printf("IPPROTO: %d    (1=ICMP, 6=TCP, 17=UDP; 50=ESP, see netinet/in.h)\n",
			*(((mblk_t *)arg0)->b_rptr+9));
	printf("Src IP address: %d.%d.%d.%d\n",
			*(((mblk_t *)arg0)->b_rptr+12),
			*(((mblk_t *)arg0)->b_rptr+13),
			*(((mblk_t *)arg0)->b_rptr+14),
			*(((mblk_t *)arg0)->b_rptr+15));
	printf("Dst IP address: %d.%d.%d.%d\n",
			*(((mblk_t *)arg0)->b_rptr+16),
			*(((mblk_t *)arg0)->b_rptr+17),
			*(((mblk_t *)arg0)->b_rptr+18),
			*(((mblk_t *)arg0)->b_rptr+19));

	printf("Src port: %d\n", (self->ipproto == 6 || self->ipproto == 17) ?
			ntohs(*(uint16_t *)(((mblk_t *)arg0)->b_rptr +
					self->hdr_len)) : 0);
	printf("Dst port: %d\n", (self->ipproto == 6 || self->ipproto == 17) ?
			ntohs(*(uint16_t *)(((mblk_t *)arg0)->b_rptr +
					self->hdr_len + 2)) : 0);
	printf("Packet len: %d\n", (((mblk_t *)arg0)->b_wptr - ((mblk_t
						*)arg0)->b_rptr));
	printf("Dropped by: %s\n", stringof(((ipdropper_t *)arg4)->ipd_name));
	printf("----------------------------------------------------------------------");
}
