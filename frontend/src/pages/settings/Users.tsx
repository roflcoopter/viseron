import AddIcon from "@mui/icons-material/Add";
import Container from "@mui/material/Container";
import Fab from "@mui/material/Fab";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell, { tableCellClasses } from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import { styled, useTheme } from "@mui/material/styles";
import { useState } from "react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import AddUserDialog from "components/settings/user/AddUserDialog";
import UserDialog from "components/settings/user/UserDialog";
import { useTitle } from "hooks/UseTitle";
import { useAuthUsers } from "lib/api/auth";
import * as types from "lib/types";

const StyledTableCell = styled(TableCell)(() => ({
  [`&.${tableCellClasses.body}`]: {
    fontSize: 14,
    verticalAlign: "top",
    overflowWrap: "anywhere",
  },
}));

function Users() {
  useTitle("Users");
  const theme = useTheme();
  const authUsers = useAuthUsers();
  const [selectedUser, setSelectedUser] =
    useState<types.AuthUserResponse | null>(null);
  const [isAddUserOpen, setIsAddUserOpen] = useState(false);

  if (authUsers.isLoading) {
    return <Loading text="Loading Users" />;
  }

  if (authUsers.isError || !authUsers.data) {
    return (
      <ErrorMessage
        text="Error loading users"
        subtext={authUsers.error?.message || authUsers.error?.message}
      />
    );
  }

  const handleRowClick = (user: types.AuthUserResponse) => {
    setSelectedUser(user);
  };

  const handleDialogClose = () => {
    setSelectedUser(null);
  };

  const handleOpenAddUser = () => {
    setIsAddUserOpen(true);
  };

  const handleCloseAddUser = () => {
    setIsAddUserOpen(false);
  };

  return (
    <Container maxWidth={false}>
      <TableContainer component={Paper}>
        <Table
          sx={() => ({
            [`& .${tableCellClasses.root}`]: {
              border: `1px solid ${theme.palette.background.default}`,
            },
            tableLayout: "fixed",
          })}
        >
          <TableHead>
            <TableRow>
              <StyledTableCell>Display Name</StyledTableCell>
              <StyledTableCell>Username</StyledTableCell>
              <StyledTableCell>Role</StyledTableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {authUsers.data.users.map((user) => (
              <TableRow
                key={user.username}
                hover
                role="button"
                onClick={() => handleRowClick(user)}
                sx={{
                  cursor: "pointer",
                }}
              >
                <StyledTableCell>{user.name}</StyledTableCell>
                <StyledTableCell>{user.username}</StyledTableCell>
                <StyledTableCell>{user.role}</StyledTableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {selectedUser && (
        <UserDialog user={selectedUser} onClose={handleDialogClose} />
      )}
      <Fab
        variant="extended"
        color="primary"
        aria-label="add"
        sx={{ zIndex: 100, position: "fixed", bottom: 16, right: 16 }}
        onClick={handleOpenAddUser}
      >
        <AddIcon />
        Add User
      </Fab>
      {isAddUserOpen && <AddUserDialog onClose={handleCloseAddUser} />}
    </Container>
  );
}

export default Users;
